"""FastAPI transport for the Jev-compatible decision contract."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from jev_gate.adapters.demo import DemoAdapter
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


def create_app(engine: DecisionEngine | None = None) -> FastAPI:
    """Create an app with an injectable decision engine."""
    decision_engine = engine or DecisionEngine((DemoAdapter(),))
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
    def decisions(request: DecisionRequest) -> DecisionResponse:
        try:
            return decision_engine.decide(request)
        except UnknownModelError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except UnsupportedCapabilityError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except BackendUnavailableError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    return api


app = create_app()
