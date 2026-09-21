"""FastAPI transport for the Jev-compatible decision contract."""

from __future__ import annotations

import os
from time import perf_counter

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from jev_gate.adapters.demo import DemoAdapter
from jev_gate.batching import MicroBatcher
from jev_gate.core import (
    BackendUnavailableError,
    DecisionEngine,
    UnknownModelError,
    UnsupportedCapabilityError,
)
from jev_gate.schemas import (
    DecisionRequest,
    DecisionResponse,
    HealthResponse,
    ModelListResponse,
)


def create_app(
    engine: DecisionEngine | None = None,
    batcher: MicroBatcher | None = None,
) -> FastAPI:
    """Create an app with an injectable decision engine and batcher."""
    decision_engine = engine or _default_engine()
    active_batcher = batcher
    if active_batcher is None and engine is None:
        if os.getenv("JEV_GATE_BATCH_ENABLED", "1") != "0":
            active_batcher = MicroBatcher(
                window_ms=float(os.getenv("JEV_GATE_BATCH_WINDOW_MS", "8")),
                max_rows=int(os.getenv("JEV_GATE_BATCH_MAX_ROWS", "32")),
                timeout_ms=float(os.getenv("JEV_GATE_REQUEST_TIMEOUT_MS", "10000")),
            )
    api = FastAPI(
        title="Jev Gate",
        version="0.1.0",
        description="An unofficial Jev-compatible typed-decision gateway.",
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

    @api.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @api.get("/v1/models", response_model=ModelListResponse)
    def models() -> ModelListResponse:
        return ModelListResponse(data=decision_engine.models())

    @api.post("/v1/decisions", response_model=DecisionResponse)
    async def decisions(request: DecisionRequest) -> DecisionResponse:
        started = perf_counter()
        try:
            adapter, normalized = decision_engine.resolve_request(request)
            if active_batcher is None:
                return decision_engine.build_response(
                    request,
                    adapter.decide(normalized),
                    diagnostics={
                        "adapter": adapter.model_info.backend,
                        "probability_source": "adapter",
                    },
                    latency_ms=(perf_counter() - started) * 1000,
                )
            outcome = await active_batcher.submit(adapter, normalized)
            return decision_engine.build_response(
                request,
                outcome.decisions,
                diagnostics={
                    "adapter": adapter.model_info.backend,
                    "probability_source": "adapter",
                    "queue_ms": outcome.queue_ms,
                    "forward_ms": outcome.forward_ms,
                    "scoring_ms": outcome.scoring_ms,
                    "batch_rows": outcome.batch_rows,
                },
                latency_ms=(perf_counter() - started) * 1000,
            )
        except UnknownModelError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except UnsupportedCapabilityError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except BackendUnavailableError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    return api


def _default_engine() -> DecisionEngine:
    model_id = os.getenv("JEV_GATE_MODEL", "demo")
    if model_id == "demo":
        return DecisionEngine((DemoAdapter(),))

    from jev_gate.adapters.qwen35 import Qwen35Adapter

    device = os.getenv("JEV_GATE_DEVICE", "cuda")
    return DecisionEngine((Qwen35Adapter(model_id=model_id, device=device),))


app = create_app()
