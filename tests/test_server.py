import asyncio

import httpx

from jev_gate.adapters.demo import DemoAdapter
from jev_gate.core import BackendUnavailableError, DecisionEngine
from jev_gate.schemas import ModelInfo
from jev_gate.server import create_app


def app(engine=None):
    return create_app(engine or DecisionEngine((DemoAdapter(),)))


def request(method: str, path: str, *, engine=None, **kwargs) -> httpx.Response:
    async def send_request() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app(engine)),
            base_url="http://test",
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send_request())


def test_health_reports_ok():
    response = request("GET", "/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_models_lists_adapter_capabilities():
    response = request("GET", "/v1/models")

    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == "demo"
    assert response.json()["data"][0]["modalities"] == ["text", "image", "video"]


def test_decisions_accepts_text_state_shorthand():
    response = request(
        "POST",
        "/v1/decisions",
        json={
            "model": "demo",
            "state": "A payment incident is under investigation.",
            "questions": [
                {
                    "id": "team",
                    "type": "choice",
                    "prompt": "Which team should handle this?",
                    "options": [
                        {"id": "technical", "text": "Technical support"},
                        {"id": "billing", "text": "Billing support"},
                    ],
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["decisions"][0]["selected"] == "technical"


def test_decisions_accepts_native_content_part_list():
    response = request(
        "POST",
        "/v1/decisions",
        json={
            "model": "demo",
            "state": [
                {"type": "text", "text": "Review this incident."},
                {"type": "image", "uri": "file:///tmp/screenshot.png"},
            ],
            "questions": [
                {
                    "id": "severity",
                    "type": "score",
                    "prompt": "What is the severity?",
                    "levels": ["low", "high"],
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["decisions"][0]["selected"] == "low"


def test_unknown_models_return_not_found():
    response = request(
        "POST",
        "/v1/decisions",
        json={
            "model": "missing",
            "state": "state",
            "questions": [
                {
                    "id": "team",
                    "type": "choice",
                    "prompt": "Choose.",
                    "options": [
                        {"id": "a", "text": "A"},
                        {"id": "b", "text": "B"},
                    ],
                }
            ],
        },
    )

    assert response.status_code == 404


def test_malformed_requests_return_bad_request():
    response = request(
        "POST",
        "/v1/decisions",
        json={"model": "demo", "state": "state", "questions": []},
    )

    assert response.status_code == 400


def test_unsupported_capabilities_return_unprocessable_entity():
    class TextOnlyAdapter(DemoAdapter):
        model_info = ModelInfo(
            id="text-only",
            backend="test",
            modalities=("text",),
            decision_types=("choice", "score", "noul"),
        )

    response = request(
        "POST",
        "/v1/decisions",
        engine=DecisionEngine((TextOnlyAdapter(),)),
        json={
            "model": "text-only",
            "state": [{"type": "image", "uri": "file:///tmp/image.png"}],
            "questions": [
                {
                    "id": "team",
                    "type": "choice",
                    "prompt": "Choose.",
                    "options": [
                        {"id": "a", "text": "A"},
                        {"id": "b", "text": "B"},
                    ],
                }
            ],
        },
    )

    assert response.status_code == 422


def test_unavailable_backends_return_service_unavailable():
    class UnavailableAdapter:
        model_info = ModelInfo(
            id="unavailable",
            backend="test",
            modalities=("text",),
            decision_types=("choice", "score", "noul"),
        )

        def decide(self, request):
            raise BackendUnavailableError("backend is offline")

    response = request(
        "POST",
        "/v1/decisions",
        engine=DecisionEngine((UnavailableAdapter(),)),
        json={
            "model": "unavailable",
            "state": "state",
            "questions": [
                {
                    "id": "team",
                    "type": "choice",
                    "prompt": "Choose.",
                    "options": [
                        {"id": "a", "text": "A"},
                        {"id": "b", "text": "B"},
                    ],
                }
            ],
        },
    )

    assert response.status_code == 503
