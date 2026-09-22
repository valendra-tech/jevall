import asyncio
import logging

import httpx

from jevall.adapters.demo import DemoAdapter
from jevall.batching import MicroBatcher
from jevall.core import BackendUnavailableError, DecisionEngine
from jevall.schemas import ModelInfo
from jevall.server import create_app


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
    assert response.json() == {"status": "ok", "model": "demo", "ready": True}


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


async def send(app_instance, method: str, path: str, **kwargs) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app_instance),
        base_url="http://test",
    ) as client:
        return await client.request(method, path, **kwargs)


def batched_app(batcher, engine=None):
    return create_app(engine or DecisionEngine((DemoAdapter(),)), batcher=batcher)


def batched_payload(question_id: str = "team"):
    return {
        "model": "demo",
        "state": "A payment incident is under investigation.",
        "questions": [
            {
                "id": question_id,
                "type": "choice",
                "prompt": "Which team should handle this?",
                "options": [
                    {"id": "technical", "text": "Technical support"},
                    {"id": "billing", "text": "Billing support"},
                ],
            }
        ],
    }


def test_batched_endpoint_serves_concurrent_requests():
    batcher = MicroBatcher(window_ms=50, max_rows=8)
    app_instance = batched_app(batcher)

    async def send_two():
        transport = httpx.ASGITransport(app=app_instance)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await asyncio.gather(
                client.post("/v1/decisions", json=batched_payload("team")),
                client.post("/v1/decisions", json=batched_payload("team-2")),
            )

    first, second = asyncio.run(send_two())

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["decisions"][0]["id"] == "team"
    assert second.json()["decisions"][0]["id"] == "team-2"
    assert first.json()["diagnostics"]["batch_rows"] == 2
    assert "queue_ms" in first.json()["diagnostics"]
    assert "forward_ms" in first.json()["diagnostics"]
    assert "scoring_ms" in first.json()["diagnostics"]


def test_batched_endpoint_maps_timeouts_to_service_unavailable():
    batcher = MicroBatcher(window_ms=50, timeout_ms=1)
    app_instance = batched_app(batcher)

    response = asyncio.run(
        send(app_instance, "POST", "/v1/decisions", json=batched_payload())
    )

    assert response.status_code == 503


def test_health_reports_device_and_dtype_when_available():
    class GpuDemoAdapter(DemoAdapter):
        device = "cuda"
        dtype = "bfloat16"

    app_instance = create_app(DecisionEngine((GpuDemoAdapter(),)))

    response = asyncio.run(send(app_instance, "GET", "/health"))

    assert response.json() == {
        "status": "ok",
        "model": "demo",
        "device": "cuda",
        "dtype": "bfloat16",
        "ready": True,
    }


def test_decisions_logs_a_summary_line(caplog):
    app_instance = batched_app(MicroBatcher(window_ms=10, max_rows=8))

    with caplog.at_level(logging.INFO, logger="jevall.server"):
        asyncio.run(
            send(app_instance, "POST", "/v1/decisions", json=batched_payload())
        )

    lines = [
        line
        for line in caplog.text.splitlines()
        if "decision id=dec_" in line
    ]
    assert len(lines) == 1
    assert "model=demo" in lines[0]
    assert "questions=1" in lines[0]
    assert "selected=['technical']" in lines[0]
