from contextlib import contextmanager, nullcontext
from types import SimpleNamespace

import pytest

import jev_gate.adapters.qwen35 as qwen35
from jev_gate.adapters.qwen35 import Qwen35Adapter, resolve_label_token_ids
from jev_gate.core import BackendUnavailableError
from jev_gate.schemas import (
    ChoiceQuestion,
    DecisionRequest,
    ImagePart,
    TextPart,
)


class FakeTokenizer:
    ids = {" A": 101, " B": 102, " C": 103, " D": 104, " E": 105}

    def __call__(self, text, *, add_special_tokens=False):
        assert add_special_tokens is False
        if text.startswith("rendered-"):
            base = 900 if text.startswith("rendered-q1") else 901
            if text.endswith(("A", "B")):
                return {"input_ids": [base, self.ids[f" {text[-1]}"]]}
            return {"input_ids": [base]}
        if " ANSWER:" in text:
            if text.endswith((" A", " B")):
                return {"input_ids": [902, self.ids[text[-2:]]]}
            return {"input_ids": [902]}
        return {"input_ids": [self.ids[text]]}

    def decode(self, token_ids, *, clean_up_tokenization_spaces=False):
        assert clean_up_tokenization_spaces is False
        return {token_id: surface for surface, token_id in self.ids.items()}[
            token_ids[0]
        ]


def request() -> DecisionRequest:
    return DecisionRequest(
        model="Qwen/Qwen3.5-9B",
        state=[
            TextPart(type="text", text="Review this checkout incident."),
            ImagePart(type="image", uri="file:///tmp/screenshot.png"),
        ],
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
        ),
    )


def test_qwen_adapter_declares_native_text_image_and_video_capabilities():
    adapter = Qwen35Adapter(
        model_id="Qwen/Qwen3.5-9B",
        device="cuda",
        model=object(),
        processor=object(),
    )

    assert adapter.model_info.id == "Qwen/Qwen3.5-9B"
    assert adapter.model_info.backend == "qwen35-transformers"
    assert adapter.model_info.modalities == ("text", "image", "video")


def test_qwen_adapter_builds_native_content_parts_without_flattening_media():
    adapter = Qwen35Adapter(
        model_id="Qwen/Qwen3.5-9B",
        device="cuda",
        model=object(),
        processor=object(),
    )

    conversation = adapter.build_conversation(request(), request().questions[0])
    content = conversation[0]["content"]

    assert content[0] == {
        "type": "text",
        "text": "Review this checkout incident.",
    }
    assert content[1] == {
        "type": "image",
        "url": "/tmp/screenshot.png",
    }
    assert content[-1]["type"] == "text"
    assert "Which team should handle this?" in content[-1]["text"]


def test_label_resolution_uses_existing_single_tokens_only():
    assert resolve_label_token_ids(FakeTokenizer(), 3) == (101, 102, 103)


def test_label_resolution_only_tokenizes_the_prefix_tail():
    seen = []

    class TailTokenizer:
        def __call__(self, text, *, add_special_tokens=False):
            assert add_special_tokens is False
            seen.append(text)
            if text.endswith((" A", " B")):
                return {"input_ids": [77, 101 if text.endswith(" A") else 102]}
            return {"input_ids": [77]}

        def decode(self, token_ids, *, clean_up_tokenization_spaces=False):
            assert clean_up_tokenization_spaces is False
            return {101: " A", 102: " B"}[token_ids[0]]

    long_prefix = "rendered prompt " * 400 + "ANSWER:"

    assert resolve_label_token_ids(TailTokenizer(), 2, prefix=long_prefix) == (
        101,
        102,
    )
    assert seen
    assert all(len(text) <= 160 for text in seen)


class FakeTensor:
    device = "cpu"
    dtype = "float"

    def __init__(self, data):
        self.data = data

    def __rsub__(self, value):
        return FakeTensor([value - item for item in self.data])

    @property
    def ndim(self):
        value = self.data
        dimensions = 0
        while isinstance(value, list):
            dimensions += 1
            value = value[0] if value else None
        return dimensions

    @property
    def shape(self):
        value = self.data
        dimensions = []
        while isinstance(value, list):
            dimensions.append(len(value))
            value = value[0] if value else None
        return tuple(dimensions)

    def to(self, *args, **kwargs):
        return self

    def __getitem__(self, index):
        if isinstance(index, tuple):
            row, position = index
            row = row.data if isinstance(row, FakeTensor) else row
            position = (
                position.data if isinstance(position, FakeTensor) else position
            )
            return FakeTensor(self.data[row][position])
        if isinstance(index, FakeTensor):
            return FakeTensor([self.data[item] for item in index.data])
        return FakeTensor(self.data[index])

    def float(self):
        return self

    def detach(self):
        return self

    def cpu(self):
        return self

    def tolist(self):
        return self.data

    def __matmul__(self, other):
        return FakeTensor(
            [
                sum(left * right for left, right in zip(row, other.data))
                for row in self.data
            ]
            if self.data and isinstance(self.data[0], list)
            else sum(left * right for left, right in zip(self.data, other.data))
        )


class FakeTorch:
    long = "long"

    @staticmethod
    def inference_mode():
        return nullcontext()

    @staticmethod
    def tensor(data, *, device, dtype):
        assert device == "cpu"
        assert dtype == "long"
        return FakeTensor(list(data))

    @staticmethod
    def flip(tensor, *, dims):
        assert dims == (-1,)
        return FakeTensor([list(reversed(row)) for row in tensor.data])

    @staticmethod
    def matmul(left, right):
        return left @ right

    @staticmethod
    def stack(tensors):
        return FakeTensor([list(tensor.data) for tensor in tensors])

    @staticmethod
    def softmax(tensor, dim):
        assert dim == -1
        maximum = max(tensor.data)
        import math

        values = [math.exp(value - maximum) for value in tensor.data]
        total = sum(values)
        return FakeTensor([value / total for value in values])

    @staticmethod
    def argmax(tensor, dim=None):
        if dim is not None:
            assert dim == -1
            return FakeTensor(
                [row.index(max(row)) for row in tensor.data]
            )
        return SimpleNamespace(item=lambda: tensor.data.index(max(tensor.data)))


class GuardedTorch(FakeTorch):
    active = False

    @classmethod
    @contextmanager
    def inference_mode(cls):
        cls.active = True
        try:
            yield
        finally:
            cls.active = False

    @classmethod
    def matmul(cls, left, right):
        assert cls.active, "Qwen scoring must stay inside inference_mode"
        return left @ right


class FakeBatch(dict):
    def to(self, device):
        assert device == "cpu"
        return self


class RecordingProcessor:
    tokenizer = FakeTokenizer()

    def __init__(self):
        self.calls = []
        self.pixel_values = object()

    def apply_chat_template(self, conversations, **kwargs):
        self.calls.append(kwargs)
        if kwargs["tokenize"] is False:
            return ["rendered-q1", "rendered-q2"]
        return FakeBatch(
            input_ids=FakeTensor([[1, 2, 3], [1, 2, 0]]),
            attention_mask=FakeTensor([[1, 1, 1], [0, 1, 1]]),
            pixel_values=self.pixel_values,
        )


class RecordingBackbone:
    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        assert kwargs["output_hidden_states"] is False
        assert kwargs["return_dict"] is True
        assert kwargs["use_cache"] is False
        return SimpleNamespace(
            last_hidden_state=FakeTensor(
                [
                    [[0.0, 0.0], [0.0, 0.0], [1.0, 0.0]],
                    [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]],
                ]
            )
        )


class RecordingModel:
    def __init__(self):
        self.model = RecordingBackbone()
        weights = [[0.0, 0.0] for _ in range(103)]
        weights[101] = [5.0, 0.0]
        weights[102] = [0.0, 5.0]
        self.output_embeddings = SimpleNamespace(weight=FakeTensor(weights))

    def get_output_embeddings(self):
        return self.output_embeddings

    def __call__(self, **kwargs):
        raise AssertionError("Qwen adapter must use the backbone projection path")


class InvalidBackboneModel:
    def model(self, **kwargs):
        return SimpleNamespace(last_hidden_state=FakeTensor([[0.0]]))

    def get_output_embeddings(self):
        return SimpleNamespace(weight=FakeTensor([[0.0, 0.0]]))


def test_qwen_decide_disables_thinking_and_uses_last_unpadded_token(monkeypatch):
    processor = RecordingProcessor()
    adapter = Qwen35Adapter(
        model_id="Qwen/Qwen3.5-9B",
        device="cpu",
        model=RecordingModel(),
        processor=processor,
    )
    base = request()
    two_questions = base.model_copy(
        update={
            "questions": (
                base.questions[0],
                base.questions[0].model_copy(update={"id": "team-2"}),
            )
        }
    )
    monkeypatch.setattr(qwen35, "_load_torch", lambda: FakeTorch)

    results = adapter.decide(two_questions)

    assert [result.selected for result in results] == ["technical", "billing"]
    assert len(adapter.model.model.calls) == 1
    assert adapter.model.model.calls[0]["pixel_values"] is processor.pixel_values
    assert all(
        call["enable_thinking"] is False
        for call in processor.calls
    )
    assert processor.calls[1]["processor_kwargs"] == {"padding": True}


def test_qwen_decide_scores_inside_inference_mode(monkeypatch):
    processor = RecordingProcessor()
    adapter = Qwen35Adapter(
        model_id="Qwen/Qwen3.5-9B",
        device="cpu",
        model=RecordingModel(),
        processor=processor,
    )
    monkeypatch.setattr(qwen35, "_load_torch", lambda: GuardedTorch)
    base = request()
    two_questions = base.model_copy(
        update={
            "questions": (
                base.questions[0],
                base.questions[0].model_copy(update={"id": "team-2"}),
            )
        }
    )

    results = adapter.decide(two_questions)

    assert results[0].selected == "technical"


def test_qwen_decide_batch_uses_single_forward_for_multiple_requests(monkeypatch):
    processor = RecordingProcessor()
    adapter = Qwen35Adapter(
        model_id="Qwen/Qwen3.5-9B",
        device="cpu",
        model=RecordingModel(),
        processor=processor,
    )
    monkeypatch.setattr(qwen35, "_load_torch", lambda: FakeTorch)
    base = request()
    second = base.model_copy(
        update={
            "questions": (
                base.questions[0].model_copy(update={"id": "team-2"}),
            )
        }
    )

    batch = adapter.decide_batch((base, second))

    assert batch.rows == 2
    assert len(adapter.model.model.calls) == 1
    assert [result.selected for result in batch.decisions[0]] == ["technical"]
    assert [result.selected for result in batch.decisions[1]] == ["billing"]
    assert batch.forward_ms >= 0.0
    assert batch.scoring_ms >= 0.0


def test_qwen_decide_maps_invalid_backbone_output_to_backend_unavailable(monkeypatch):
    adapter = Qwen35Adapter(
        model_id="Qwen/Qwen3.5-9B",
        device="cpu",
        model=InvalidBackboneModel(),
        processor=RecordingProcessor(),
    )
    monkeypatch.setattr(qwen35, "_load_torch", lambda: FakeTorch)

    with pytest.raises(BackendUnavailableError, match="unexpected hidden"):
        adapter.decide(request())


class CountingProcessor(RecordingProcessor):
    def apply_chat_template(self, conversations, **kwargs):
        self.calls.append(kwargs)
        if kwargs["tokenize"] is False:
            return [f"rendered-{index}" for index in range(len(conversations))]
        rows = len(conversations)
        return FakeBatch(
            input_ids=FakeTensor([[1, 2, 3] for _ in range(rows)]),
            attention_mask=FakeTensor([[1, 1, 1] for _ in range(rows)]),
            pixel_values=self.pixel_values,
        )


class CountingBackbone:
    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        rows = kwargs["input_ids"].shape[0]
        return SimpleNamespace(
            last_hidden_state=FakeTensor(
                [[[0.0, 0.0], [0.0, 0.0], [1.0, 0.0]] for _ in range(rows)]
            )
        )


class CountingModel:
    def __init__(self):
        self.model = CountingBackbone()
        weights = [[0.0, 0.0] for _ in range(103)]
        weights[101] = [5.0, 0.0]
        weights[102] = [0.0, 5.0]
        self.output_embeddings = SimpleNamespace(weight=FakeTensor(weights))

    def get_output_embeddings(self):
        return self.output_embeddings


def test_qwen_decide_batch_pads_rows_to_bucket(monkeypatch):
    processor = CountingProcessor()
    adapter = Qwen35Adapter(
        model_id="Qwen/Qwen3.5-9B",
        device="cpu",
        model=CountingModel(),
        processor=processor,
    )
    monkeypatch.setattr(qwen35, "_load_torch", lambda: FakeTorch)
    base = request()
    three_questions = base.model_copy(
        update={
            "questions": (
                base.questions[0],
                base.questions[0].model_copy(update={"id": "team-2"}),
                base.questions[0].model_copy(update={"id": "team-3"}),
            )
        }
    )

    batch = adapter.decide_batch((three_questions,))

    assert adapter.model.model.calls[0]["input_ids"].shape[0] == 4
    assert [result.id for result in batch.decisions[0]] == [
        "team",
        "team-2",
        "team-3",
    ]
    assert batch.rows == 3


def test_qwen_warmup_drives_decide_batch_for_each_row_count(monkeypatch):
    processor = RecordingProcessor()
    adapter = Qwen35Adapter(
        model_id="Qwen/Qwen3.5-9B",
        device="cpu",
        model=RecordingModel(),
        processor=processor,
    )
    monkeypatch.setattr(qwen35, "_load_torch", lambda: FakeTorch)
    counts = []
    original = adapter.decide_batch

    def spy(requests):
        counts.append(len(requests[0].questions))
        return original(requests)

    monkeypatch.setattr(adapter, "decide_batch", spy)

    adapter.warmup((2,))

    assert counts == [2]
