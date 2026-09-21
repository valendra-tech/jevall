"""Qwen 3.5 Transformers adapter with native multimodal inputs."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from time import perf_counter
from typing import Any
from urllib.parse import unquote, urlparse

from jevall.adapters.base import AdapterBatch
from jevall.core import BackendUnavailableError
from jevall.devices import resolve_device, resolve_dtype
from jevall.models import ensure_model
from jevall.schemas import (
    ChoiceQuestion,
    DecisionRequest,
    DecisionResult,
    ImagePart,
    ModelInfo,
    NoulQuestion,
    Question,
    ScoreQuestion,
    TextPart,
    VideoPart,
)

_PREFIX_TAIL_CHARS = 64
_WARMUP_ROW_COUNTS = (1, 2, 4, 8, 16, 32)
_ROW_BUCKETS = _WARMUP_ROW_COUNTS


def _bucket_rows(row_count: int) -> int:
    for bucket in _ROW_BUCKETS:
        if row_count <= bucket:
            return bucket
    return row_count


def _warmup_request(question_count: int) -> DecisionRequest:
    options = (
        {"id": "alpha", "text": "Alpha"},
        {"id": "beta", "text": "Beta"},
    )
    return DecisionRequest(
        model="warmup",
        state="Warmup state.",
        questions=tuple(
            ChoiceQuestion(
                id=f"warmup-{index}",
                type="choice",
                prompt=f"Warmup question {index}?",
                options=options,
            )
            for index in range(question_count)
        ),
    )


logger = logging.getLogger(__name__)


def _load_torch():
    try:
        import torch
    except ImportError as error:
        raise BackendUnavailableError(
            "Qwen adapter requires the qwen optional dependencies"
        ) from error
    return torch


def _token_ids(encoded: Any) -> tuple[int, ...]:
    if isinstance(encoded, Mapping):
        encoded = encoded["input_ids"]
    else:
        encoded = getattr(encoded, "input_ids")
    if hasattr(encoded, "tolist"):
        encoded = encoded.tolist()
    while encoded and isinstance(encoded[0], (list, tuple)):
        encoded = encoded[0]
    return tuple(int(token_id) for token_id in encoded)


def _prefix_tail(prefix: str) -> str:
    """Keep only the boundary context that decides the appended label token."""
    return prefix[-_PREFIX_TAIL_CHARS:]


def resolve_label_token_ids(
    tokenizer: Any,
    count: int,
    *,
    prefix: str | None = None,
    prefixes: tuple[str, ...] | None = None,
) -> tuple[int, ...]:
    """Resolve existing single-token labels without mutating the tokenizer."""
    if not 2 <= count <= 5:
        raise ValueError("label count must be between 2 and 5")
    if prefix is not None and prefixes is not None:
        raise ValueError("pass either prefix or prefixes, not both")
    if prefix is not None:
        prefixes = (prefix,)
    elif prefixes is None:
        prefixes = ()
    prefix_tails = tuple(_prefix_tail(current) for current in prefixes)

    token_ids = []
    for label in "ABCDE"[:count]:
        if prefix_tails:
            resolved = None
            for surface in (f" {label}", label):
                candidate_ids = []
                for current_prefix in prefix_tails:
                    prefix_ids = _token_ids(
                        tokenizer(current_prefix, add_special_tokens=False)
                    )
                    extended_ids = _token_ids(
                        tokenizer(
                            current_prefix + surface,
                            add_special_tokens=False,
                        )
                    )
                    if (
                        len(extended_ids) != len(prefix_ids) + 1
                        or extended_ids[:-1] != prefix_ids
                    ):
                        break
                    token_id = extended_ids[-1]
                    decoded = tokenizer.decode(
                        [token_id],
                        clean_up_tokenization_spaces=False,
                    )
                    if decoded != surface:
                        break
                    candidate_ids.append(token_id)
                else:
                    if len(set(candidate_ids)) == 1:
                        resolved = candidate_ids[0]
                        break
            if resolved is None:
                raise ValueError(
                    f"label {label!r} has no stable single-token surface"
                )
            token_ids.append(resolved)
            continue

        candidates = (
            f" {label}",
            label,
        )
        resolved = None
        for surface in candidates:
            ids = _token_ids(tokenizer(surface, add_special_tokens=False))
            if len(ids) == 1:
                resolved = ids[0]
                break
        if resolved is None:
            raise ValueError(f"label {label!r} must resolve to one existing token")
        token_ids.append(resolved)
    if len(set(token_ids)) != len(token_ids):
        raise ValueError("labels must resolve to distinct token IDs")
    return tuple(token_ids)


def load_qwen35(model_id: str, device: str, dtype: str = "auto"):
    """Fetch and load a Qwen 3.5 multimodal checkpoint."""
    torch = _load_torch()
    try:
        import transformers

        auto_processor = transformers.AutoProcessor
    except ImportError as error:
        raise BackendUnavailableError(
            "Qwen adapter requires the qwen optional dependencies"
        ) from error

    model_class = getattr(transformers, "Qwen3_5ForConditionalGeneration", None)
    if model_class is None:
        model_class = getattr(transformers, "AutoModelForMultimodalLM", None)
    if model_class is None:
        raise BackendUnavailableError(
            "installed Transformers does not expose a Qwen 3.5 multimodal model"
        )

    torch_dtype = getattr(torch, resolve_dtype(dtype, device))
    local_path = ensure_model(model_id)
    logger.info(
        "model.load id=%s device=%s dtype=%s path=%s",
        model_id,
        device,
        torch_dtype,
        local_path,
    )
    started = perf_counter()
    try:
        processor = auto_processor.from_pretrained(local_path)
        model = model_class.from_pretrained(
            local_path,
            torch_dtype=torch_dtype,
            attn_implementation="sdpa",
        ).to(device)
        model.eval()
    except Exception as error:
        logger.exception("model.load failed id=%s device=%s", model_id, device)
        raise BackendUnavailableError(
            f"could not load Qwen model {model_id!r} on {device!r}"
        ) from error
    logger.info(
        "model.loaded id=%s device=%s dtype=%s elapsed=%.1fs",
        model_id,
        device,
        torch_dtype,
        perf_counter() - started,
    )
    return model, processor


class Qwen35Adapter:
    """Score independent typed questions in one Qwen forward pass."""

    def __init__(
        self,
        model_id: str = "Qwen/Qwen3.5-9B",
        device: str = "auto",
        *,
        dtype: str = "auto",
        model: Any | None = None,
        processor: Any | None = None,
    ) -> None:
        if (model is None) != (processor is None):
            raise ValueError("model and processor must be provided together")
        if model is None:
            device = resolve_device(device)
            dtype = resolve_dtype(dtype, device)
            model, processor = load_qwen35(model_id, device, dtype)
        self.model_id = model_id
        self.device = device
        self.dtype = dtype
        self.model = model
        self.processor = processor
        self.tokenizer = getattr(processor, "tokenizer", processor)
        self.model_info = ModelInfo(
            id=model_id,
            backend="qwen35-transformers",
            modalities=("text", "image", "video"),
            decision_types=("choice", "score", "noul"),
        )

    def build_conversation(
        self,
        request: DecisionRequest,
        question: Question,
    ) -> list[dict[str, Any]]:
        content: list[dict[str, str]] = []
        for part in request.normalized_state():
            if isinstance(part, TextPart):
                content.append({"type": "text", "text": part.text})
            elif isinstance(part, ImagePart):
                content.append(
                    {"type": "image", "url": self._media_source(part.uri)}
                )
            elif isinstance(part, VideoPart):
                content.append(
                    {"type": "video", "url": self._media_source(part.uri)}
                )
            else:
                raise TypeError(f"unsupported content part: {type(part).__name__}")
        content.append({"type": "text", "text": self._question_prompt(question)})
        return [{"role": "user", "content": content}]

    @staticmethod
    def _media_source(uri: str) -> str:
        parsed = urlparse(uri)
        if parsed.scheme != "file":
            return uri
        if parsed.netloc not in ("", "localhost"):
            raise ValueError("file URI host must be empty or localhost")
        return unquote(parsed.path)

    @staticmethod
    def _question_prompt(question: Question) -> str:
        if isinstance(question, ChoiceQuestion):
            option_texts = tuple(option.text for option in question.options)
        elif isinstance(question, ScoreQuestion):
            option_texts = question.levels
        elif isinstance(question, NoulQuestion):
            option_texts = ("False", "True")
        else:
            raise TypeError(f"unsupported question type: {type(question).__name__}")

        option_lines = "\n".join(
            f"{label}. {text}"
            for label, text in zip("ABCDE", option_texts)
        )
        return (
            f"QUESTION {question.id}:\n{question.prompt}\n"
            f"OPTIONS:\n{option_lines}\n"
            "Return only the single answer label.\n"
            f"DECISION:\n{question.id} ANSWER:"
        )

    def decide(self, request: DecisionRequest) -> list[DecisionResult]:
        return list(self.decide_batch((request,)).decisions[0])

    def decide_batch(
        self,
        requests: tuple[DecisionRequest, ...],
    ) -> AdapterBatch:
        if not requests:
            return AdapterBatch(
                decisions=(),
                rows=0,
                forward_ms=0.0,
                scoring_ms=0.0,
            )
        torch = _load_torch()
        conversations = []
        rows: list[tuple[int, Question]] = []
        for request_index, request in enumerate(requests):
            for question in request.questions:
                conversations.append(self.build_conversation(request, question))
                rows.append((request_index, question))
        padded_conversations = self._pad_rows(conversations)
        try:
            forward_started = perf_counter()
            rendered_prompts = self.processor.apply_chat_template(
                padded_conversations,
                add_generation_prompt=True,
                tokenize=False,
                enable_thinking=False,
            )
            if isinstance(rendered_prompts, str):
                rendered_prompts = [rendered_prompts]
            inputs = self.processor.apply_chat_template(
                padded_conversations,
                add_generation_prompt=True,
                tokenize=True,
                return_dict=True,
                return_tensors="pt",
                enable_thinking=False,
                processor_kwargs={"padding": True},
            )
            inputs = self._move_inputs(inputs)
            attention_mask = inputs["attention_mask"]
            last_positions = attention_mask.shape[-1] - 1 - torch.argmax(
                torch.flip(attention_mask, dims=(-1,)), dim=-1
            )
            with torch.inference_mode():
                outputs = self.model.model(
                    **inputs,
                    output_hidden_states=False,
                    return_dict=True,
                    use_cache=False,
                )
            forward_ms = (perf_counter() - forward_started) * 1000.0
        except BackendUnavailableError:
            raise
        except Exception as error:
            raise BackendUnavailableError(
                f"Qwen inference failed for {self.model_id!r}"
            ) from error

        scoring_started = perf_counter()
        try:
            hidden = outputs.last_hidden_state
            if getattr(hidden, "ndim", 0) != 3:
                raise BackendUnavailableError(
                    "Qwen backbone returned unexpected hidden states"
                )
            if hidden.shape[0] != len(padded_conversations):
                raise BackendUnavailableError(
                    "Qwen backbone batch size did not match question count"
                )
            output_embeddings = self.model.get_output_embeddings()
            weight = output_embeddings.weight
            if getattr(weight, "ndim", 0) != 2:
                raise BackendUnavailableError(
                    "Qwen output embeddings have unexpected shape"
                )

            probability_rows = []
            row_meta = []
            for row, (request_index, question) in enumerate(rows):
                labels, keys = self._labels_and_keys(question)
                try:
                    token_ids = resolve_label_token_ids(
                        self.tokenizer,
                        len(labels),
                        prefixes=(
                            f"{question.id} ANSWER:",
                            rendered_prompts[row],
                        ),
                    )
                except (TypeError, ValueError) as error:
                    raise BackendUnavailableError(
                        "Qwen labels must resolve to existing single tokens"
                    ) from error
                candidate_ids = torch.tensor(
                    token_ids,
                    device=weight.device,
                    dtype=torch.long,
                )
                candidate_rows = weight[candidate_ids]
                selected_hidden = hidden[row, last_positions[row]]
                if selected_hidden.dtype != candidate_rows.dtype:
                    selected_hidden = selected_hidden.to(dtype=candidate_rows.dtype)
                with torch.inference_mode():
                    candidate_logits = torch.matmul(
                        candidate_rows,
                        selected_hidden,
                    ).float()
                    probabilities = torch.softmax(candidate_logits.float(), dim=-1)
                probability_rows.append(probabilities)
                row_meta.append((request_index, question, keys))
            with torch.inference_mode():
                groups: dict[int, list[int]] = {}
                for index, (_, _, keys) in enumerate(row_meta):
                    groups.setdefault(len(keys), []).append(index)
                selected_indices = [0] * len(row_meta)
                probability_values: list[list[float]] = [
                    [] for _ in row_meta
                ]
                for indices in groups.values():
                    stacked = torch.stack(
                        [probability_rows[index] for index in indices]
                    )
                    group_selected = torch.argmax(stacked, dim=-1).tolist()
                    group_values = stacked.tolist()
                    for position, index in enumerate(indices):
                        selected_indices[index] = group_selected[position]
                        probability_values[index] = group_values[position]
            grouped: list[list[DecisionResult]] = [[] for _ in requests]
            for index, (request_index, question, keys) in enumerate(row_meta):
                probability_map = {
                    key: float(value)
                    for key, value in zip(keys, probability_values[index])
                }
                selected = keys[selected_indices[index]]
                if isinstance(question, NoulQuestion):
                    selected = selected == "true"
                grouped[request_index].append(
                    DecisionResult(
                        id=question.id,
                        type=question.type,
                        selected=selected,
                        probabilities=probability_map,
                    )
                )
            scoring_ms = (perf_counter() - scoring_started) * 1000.0
            return AdapterBatch(
                decisions=tuple(tuple(results) for results in grouped),
                rows=len(rows),
                forward_ms=forward_ms,
                scoring_ms=scoring_ms,
            )
        except BackendUnavailableError:
            raise
        except Exception as error:
            raise BackendUnavailableError(
                f"Qwen decision scoring failed for {self.model_id!r}"
            ) from error

    def warmup(self, row_counts: tuple[int, ...] = _WARMUP_ROW_COUNTS) -> None:
        """Compile backend kernels for the batch shapes used at runtime."""
        for row_count in row_counts:
            self.decide_batch((_warmup_request(row_count),))

    @staticmethod
    def _pad_rows(conversations: list[Any]) -> list[Any]:
        bucket = _bucket_rows(len(conversations))
        if bucket <= len(conversations):
            return conversations
        padding = conversations[-1]
        return conversations + [padding] * (bucket - len(conversations))

    def _move_inputs(self, inputs: Any) -> Any:
        mover = getattr(inputs, "to", None)
        if callable(mover):
            return mover(self.device)
        if isinstance(inputs, Mapping):
            return {
                key: value.to(self.device) if hasattr(value, "to") else value
                for key, value in inputs.items()
            }
        raise TypeError("Qwen processor output must be a mapping or support .to()")

    @staticmethod
    def _labels_and_keys(question: Question) -> tuple[tuple[str, ...], tuple[str, ...]]:
        if isinstance(question, ChoiceQuestion):
            keys = tuple(option.id for option in question.options)
        elif isinstance(question, ScoreQuestion):
            keys = tuple(question.levels)
        elif isinstance(question, NoulQuestion):
            keys = ("false", "true")
        else:
            raise TypeError(f"unsupported question type: {type(question).__name__}")
        return tuple("ABCDE"[: len(keys)]), keys
