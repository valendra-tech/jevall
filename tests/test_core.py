import pytest

from jev_gate.adapters.demo import DemoAdapter
from jev_gate.core import (
    AdapterContractError,
    DecisionEngine,
    UnknownModelError,
    UnsupportedCapabilityError,
)
from jev_gate.schemas import (
    ChoiceQuestion,
    DecisionRequest,
    DecisionResult,
    ImagePart,
    ModelInfo,
    NoulQuestion,
    ScoreQuestion,
)


def request() -> DecisionRequest:
    return DecisionRequest(
        model="demo",
        state="A payment incident is under investigation.",
        questions=(
            ChoiceQuestion(
                id="team",
                type="choice",
                prompt="Which team should handle this?",
                options=(
                    {"id": "technical", "text": "Technical support"},
                    {"id": "billing", "text": "Billing support"},
                ),
            ),
            ScoreQuestion(
                id="severity",
                type="score",
                prompt="What is the severity?",
                levels=("low", "high"),
            ),
            NoulQuestion(
                id="refund",
                type="noul",
                prompt="Did the customer request a refund?",
            ),
        ),
    )


def test_engine_lists_registered_models_and_rejects_unknown_models():
    engine = DecisionEngine((DemoAdapter(),))

    assert [model.id for model in engine.models()] == ["demo"]
    with pytest.raises(UnknownModelError, match="unknown model: missing"):
        engine.resolve("missing")


def test_demo_adapter_returns_one_typed_result_per_question():
    response = DecisionEngine((DemoAdapter(),)).decide(request())

    assert response.model == "demo"
    assert [decision.id for decision in response.decisions] == [
        "team",
        "severity",
        "refund",
    ]
    assert [decision.type for decision in response.decisions] == [
        "choice",
        "score",
        "noul",
    ]
    assert [decision.selected for decision in response.decisions] == [
        "technical",
        "low",
        False,
    ]
    assert response.diagnostics["adapter"] == "demo"
    assert response.usage.input_tokens is None


def test_engine_normalizes_string_state_before_dispatch():
    class RecordingAdapter(DemoAdapter):
        def __init__(self):
            super().__init__()
            self.received_state = None

        def decide(self, request):
            self.received_state = request.normalized_state()
            return super().decide(request)

    adapter = RecordingAdapter()
    DecisionEngine((adapter,)).decide(request())

    assert adapter.received_state[0].type == "text"
    assert adapter.received_state[0].text.startswith("A payment incident")


def test_engine_rejects_content_not_declared_by_adapter_capabilities():
    class TextOnlyAdapter(DemoAdapter):
        model_info = ModelInfo(
            id="text-only",
            backend="test",
            modalities=("text",),
            decision_types=("choice", "score", "noul"),
        )

    image_request = request().model_copy(
        update={
            "model": "text-only",
            "state": [ImagePart(type="image", uri="file:///tmp/image.png")],
        }
    )

    with pytest.raises(UnsupportedCapabilityError, match="image"):
        DecisionEngine((TextOnlyAdapter(),)).decide(image_request)


def test_engine_rejects_invalid_adapter_results():
    class InvalidAdapter:
        model_info = ModelInfo(
            id="invalid",
            backend="test",
            modalities=("text",),
            decision_types=("choice", "score", "noul"),
        )

        def decide(self, request):
            return [{"id": "wrong", "type": "choice", "selected": False}]

    base_request = request()
    invalid_request = base_request.model_copy(
        update={
            "model": "invalid",
            "questions": (base_request.questions[0],),
        }
    )

    with pytest.raises(AdapterContractError, match="question ID"):
        DecisionEngine((InvalidAdapter(),)).decide(invalid_request)


def test_resolve_request_normalizes_state_and_returns_adapter():
    engine = DecisionEngine((DemoAdapter(),))
    base_request = request()

    adapter, normalized = engine.resolve_request(base_request)

    assert adapter.model_info.id == "demo"
    assert isinstance(normalized.state, list)
    assert normalized.state[0].type == "text"


def test_build_response_uses_supplied_diagnostics_and_latency():
    engine = DecisionEngine((DemoAdapter(),))
    base_request = request().model_copy(
        update={"questions": (request().questions[0],)}
    )
    decisions = [
        DecisionResult(
            id="team",
            type="choice",
            selected="technical",
            probabilities={"technical": 1.0, "billing": 0.0},
        )
    ]

    response = engine.build_response(
        base_request,
        decisions,
        diagnostics={"adapter": "demo", "queue_ms": 1.5},
        latency_ms=12.5,
    )

    assert response.usage.latency_ms == 12.5
    assert response.diagnostics == {"adapter": "demo", "queue_ms": 1.5}
    assert response.decisions[0].selected == "technical"
