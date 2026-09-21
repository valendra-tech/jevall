"""FastAPI transport for the Jev-compatible decision contract."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from jevall.adapters.demo import DemoAdapter
from jevall.batching import MicroBatcher
from jevall.core import (
    BackendUnavailableError,
    DecisionEngine,
    UnknownModelError,
    UnsupportedCapabilityError,
)
from jevall.schemas import (
    DecisionRequest,
    DecisionResponse,
    HealthResponse,
    ModelListResponse,
)

logger = logging.getLogger(__name__)


def _warmup_rows() -> tuple[int, ...]:
    raw = os.getenv("JEVALL_WARMUP_ROWS", "1,2,4,8,16,32")
    return tuple(int(item) for item in raw.split(",") if item.strip())


def _log_decision(
    response: DecisionResponse,
    diagnostics: dict[str, object],
) -> None:
    logger.info(
        "decision id=%s model=%s questions=%d batch_rows=%s "
        "queue_ms=%s forward_ms=%s scoring_ms=%s total_ms=%.1f selected=%s",
        response.id,
        response.model,
        len(response.decisions),
        diagnostics.get("batch_rows", 0),
        _format_ms(diagnostics.get("queue_ms")),
        _format_ms(diagnostics.get("forward_ms")),
        _format_ms(diagnostics.get("scoring_ms")),
        response.usage.latency_ms,
        [decision.selected for decision in response.decisions],
    )


def _format_ms(value: object) -> str:
    return f"{value:.1f}" if isinstance(value, (int, float)) else "n/a"


def create_app(
    engine: DecisionEngine | None = None,
    batcher: MicroBatcher | None = None,
) -> FastAPI:
    """Create an app with an injectable decision engine and batcher."""
    decision_engine = engine or _default_engine()
    active_batcher = batcher
    if active_batcher is None and engine is None:
        if os.getenv("JEVALL_BATCH_ENABLED", "1") != "0":
            active_batcher = MicroBatcher(
                window_ms=float(os.getenv("JEVALL_BATCH_WINDOW_MS", "8")),
                max_rows=int(os.getenv("JEVALL_BATCH_MAX_ROWS", "32")),
                timeout_ms=float(os.getenv("JEVALL_REQUEST_TIMEOUT_MS", "10000")),
            )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        for model in decision_engine.models():
            logger.info("serving model=%s backend=%s", model.id, model.backend)
        if active_batcher is not None:
            logger.info(
                "batcher window_ms=%s max_rows=%s timeout_ms=%s",
                active_batcher.window_ms,
                active_batcher.max_rows,
                active_batcher.timeout_ms,
            )
        if active_batcher is not None and os.getenv("JEVALL_WARMUP", "1") != "0":
            for model in decision_engine.models():
                warmup = getattr(decision_engine.resolve(model.id), "warmup", None)
                if warmup is None:
                    continue
                rows = _warmup_rows()
                logger.info("warmup start model=%s rows=%s", model.id, rows)
                started = perf_counter()
                try:
                    await active_batcher.run_exclusive(warmup, rows)
                except Exception:
                    logger.warning("warmup failed model=%s", model.id, exc_info=True)
                else:
                    logger.info(
                        "warmup done model=%s elapsed=%.1fs",
                        model.id,
                        perf_counter() - started,
                    )
        try:
            yield
        finally:
            if active_batcher is not None:
                active_batcher.close()
                logger.info("batcher closed")

    api = FastAPI(
        title="JEVALL",
        version="0.1.0",
        description="An unofficial Jev-compatible typed-decision gateway.",
        lifespan=lifespan,
    )

    @api.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        del request
        detail = [
            {
                "loc": item["loc"],
                "msg": item["msg"],
                "type": item["type"],
            }
            for item in error.errors()
        ]
        return JSONResponse(
            status_code=400,
            content=jsonable_encoder({"detail": detail}),
        )

    @api.get(
        "/health",
        response_model=HealthResponse,
        response_model_exclude_none=True,
    )
    def health() -> HealthResponse:
        models = decision_engine.models()
        if not models:
            return HealthResponse(status="ok")
        model = models[0]
        adapter = decision_engine.resolve(model.id)
        return HealthResponse(
            status="ok",
            model=model.id,
            device=getattr(adapter, "device", None),
            dtype=getattr(adapter, "dtype", None),
            ready=True,
        )

    @api.get("/v1/models", response_model=ModelListResponse)
    def models() -> ModelListResponse:
        return ModelListResponse(data=decision_engine.models())

    @api.post("/v1/decisions", response_model=DecisionResponse)
    async def decisions(request: DecisionRequest) -> DecisionResponse:
        started = perf_counter()
        try:
            adapter, normalized = decision_engine.resolve_request(request)
            if active_batcher is None:
                decisions_result = await asyncio.to_thread(
                    adapter.decide,
                    normalized,
                )
                response = decision_engine.build_response(
                    request,
                    decisions_result,
                    diagnostics={
                        "adapter": adapter.model_info.backend,
                        "probability_source": "adapter",
                    },
                    latency_ms=(perf_counter() - started) * 1000,
                )
                _log_decision(response, response.diagnostics)
                return response
            outcome = await active_batcher.submit(adapter, normalized)
            diagnostics = {
                "adapter": adapter.model_info.backend,
                "probability_source": "adapter",
                "queue_ms": outcome.queue_ms,
                "forward_ms": outcome.forward_ms,
                "scoring_ms": outcome.scoring_ms,
                "batch_rows": outcome.batch_rows,
            }
            response = decision_engine.build_response(
                request,
                outcome.decisions,
                diagnostics=diagnostics,
                latency_ms=(perf_counter() - started) * 1000,
            )
            _log_decision(response, diagnostics)
            return response
        except UnknownModelError as error:
            logger.warning("decision rejected model=%s reason=%s", request.model, error)
            raise HTTPException(status_code=404, detail=str(error)) from error
        except UnsupportedCapabilityError as error:
            logger.warning(
                "decision unsupported model=%s reason=%s",
                request.model,
                error,
            )
            raise HTTPException(status_code=422, detail=str(error)) from error
        except BackendUnavailableError as error:
            logger.error("decision failed model=%s reason=%s", request.model, error)
            raise HTTPException(status_code=503, detail=str(error)) from error

    return api


def _default_engine() -> DecisionEngine:
    model_id = os.getenv("JEVALL_MODEL", "demo")
    if model_id == "demo":
        return DecisionEngine((DemoAdapter(),))

    from jevall.adapters.qwen35 import Qwen35Adapter

    device = os.getenv("JEVALL_DEVICE", "cuda")
    return DecisionEngine((Qwen35Adapter(model_id=model_id, device=device),))


app = create_app()
