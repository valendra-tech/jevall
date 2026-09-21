"""Adapter registry and request orchestration."""

from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from pydantic import ValidationError

from jev_gate.adapters.base import DecisionAdapter
from jev_gate.schemas import (
    ChoiceQuestion,
    DecisionRequest,
    DecisionResponse,
    DecisionResult,
    NoulQuestion,
    ScoreQuestion,
    Usage,
)


class UnknownModelError(LookupError):
    """Raised when a request selects an unregistered model."""


class UnsupportedCapabilityError(ValueError):
    """Raised when an adapter does not declare a requested capability."""


class AdapterContractError(ValueError):
    """Raised when an adapter returns a result outside the public contract."""


class BackendUnavailableError(RuntimeError):
    """Raised when an adapter cannot reach or load its model backend."""


class DecisionEngine:
    """Resolve model adapters and wrap their typed results."""

    def __init__(self, adapters: tuple[DecisionAdapter, ...] = ()) -> None:
        self._adapters: dict[str, DecisionAdapter] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: DecisionAdapter) -> None:
        model_id = adapter.model_info.id
        if model_id in self._adapters:
            raise ValueError(f"model already registered: {model_id}")
        self._adapters[model_id] = adapter

    def resolve(self, model_id: str) -> DecisionAdapter:
        try:
            return self._adapters[model_id]
        except KeyError as error:
            raise UnknownModelError(f"unknown model: {model_id}") from error

    def models(self):
        return tuple(adapter.model_info for adapter in self._adapters.values())

    def decide(self, request: DecisionRequest) -> DecisionResponse:
        adapter = self.resolve(request.model)
        normalized_request = request.model_copy(
            update={"state": request.normalized_state()}
        )
        self._validate_capabilities(normalized_request, adapter)
        started = perf_counter()
        decisions = self._validate_results(
            normalized_request,
            adapter.decide(normalized_request),
        )
        elapsed_ms = (perf_counter() - started) * 1000
        return DecisionResponse(
            id=f"dec_{uuid4().hex}",
            model=request.model,
            decisions=tuple(decisions),
            usage=Usage(latency_ms=elapsed_ms),
            diagnostics={
                "adapter": adapter.model_info.backend,
                "probability_source": "adapter",
            },
        )

    @staticmethod
    def _validate_capabilities(
        request: DecisionRequest,
        adapter: DecisionAdapter,
    ) -> None:
        declared_modalities = set(adapter.model_info.modalities)
        requested_modalities = {part.type for part in request.normalized_state()}
        unsupported_modalities = sorted(requested_modalities - declared_modalities)
        if unsupported_modalities:
            raise UnsupportedCapabilityError(
                f"model {request.model!r} does not support modalities: "
                f"{', '.join(unsupported_modalities)}"
            )

        declared_decision_types = set(adapter.model_info.decision_types)
        requested_decision_types = {question.type for question in request.questions}
        unsupported_decisions = sorted(
            requested_decision_types - declared_decision_types
        )
        if unsupported_decisions:
            raise UnsupportedCapabilityError(
                f"model {request.model!r} does not support decision types: "
                f"{', '.join(unsupported_decisions)}"
            )

    @staticmethod
    def _validate_results(
        request: DecisionRequest,
        raw_decisions,
    ) -> tuple[DecisionResult, ...]:
        if not isinstance(raw_decisions, (list, tuple)):
            raise AdapterContractError("adapter results must be a list")
        if len(raw_decisions) != len(request.questions):
            raise AdapterContractError(
                "adapter result count must match question count"
            )

        validated = []
        for question, raw_decision in zip(request.questions, raw_decisions):
            try:
                decision = DecisionResult.model_validate(raw_decision)
            except ValidationError as error:
                raise AdapterContractError(
                    "adapter returned an invalid result"
                ) from error

            if decision.id != question.id:
                raise AdapterContractError(
                    f"adapter result question ID must be {question.id!r}"
                )
            if decision.type != question.type:
                raise AdapterContractError(
                    f"adapter result type must be {question.type!r}"
                )

            if isinstance(question, ChoiceQuestion):
                allowed = {option.id for option in question.options}
                if (
                    type(decision.selected) is not str
                    or decision.selected not in allowed
                ):
                    raise AdapterContractError(
                        f"choice result for {question.id!r} selected an invalid option"
                    )
            elif isinstance(question, ScoreQuestion):
                allowed = set(question.levels)
                if (
                    type(decision.selected) is not str
                    or decision.selected not in allowed
                ):
                    raise AdapterContractError(
                        f"score result for {question.id!r} selected an invalid level"
                    )
            elif isinstance(question, NoulQuestion):
                if type(decision.selected) is not bool:
                    raise AdapterContractError(
                        f"noul result for {question.id!r} must select a boolean"
                    )
                allowed = None
            else:
                raise AdapterContractError(
                    f"unsupported question type: {type(question).__name__}"
                )

            if decision.probabilities is not None:
                probability_keys = set(decision.probabilities)
                expected_keys = allowed if allowed is not None else {"true", "false"}
                if probability_keys != expected_keys:
                    raise AdapterContractError(
                        f"probability keys for {question.id!r} do not match "
                        "selection values"
                    )
                if any(
                    not 0.0 <= probability <= 1.0
                    for probability in decision.probabilities.values()
                ):
                    raise AdapterContractError(
                        f"probabilities for {question.id!r} must be between 0 and 1"
                    )
            validated.append(decision)
        return tuple(validated)
