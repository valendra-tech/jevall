"""Deterministic adapter used for local development and tests."""

from __future__ import annotations

from jevall.adapters.base import AdapterBatch
from jevall.schemas import (
    ChoiceQuestion,
    DecisionRequest,
    DecisionResult,
    ModelInfo,
    NoulQuestion,
    ScoreQuestion,
)


class DemoAdapter:
    """Return predictable typed decisions without loading a model."""

    model_info = ModelInfo(
        id="demo",
        backend="demo",
        modalities=("text", "image", "video"),
        decision_types=("choice", "score", "noul"),
    )

    def decide(self, request: DecisionRequest) -> list[DecisionResult]:
        results = []
        for question in request.questions:
            if isinstance(question, ChoiceQuestion):
                selected = question.options[0].id
                probabilities = {
                    option.id: float(option.id == selected)
                    for option in question.options
                }
                results.append(
                    DecisionResult(
                        id=question.id,
                        type=question.type,
                        selected=selected,
                        probabilities=probabilities,
                    )
                )
            elif isinstance(question, ScoreQuestion):
                selected = question.levels[0]
                probabilities = {
                    level: float(level == selected) for level in question.levels
                }
                results.append(
                    DecisionResult(
                        id=question.id,
                        type=question.type,
                        selected=selected,
                        probabilities=probabilities,
                    )
                )
            elif isinstance(question, NoulQuestion):
                results.append(
                    DecisionResult(
                        id=question.id,
                        type=question.type,
                        selected=False,
                    )
                )
            else:
                raise TypeError(f"unsupported question type: {type(question).__name__}")
        return results

    def decide_batch(
        self,
        requests: tuple[DecisionRequest, ...],
    ) -> AdapterBatch:
        decisions = tuple(tuple(self.decide(request)) for request in requests)
        return AdapterBatch(
            decisions=decisions,
            rows=sum(len(request.questions) for request in requests),
            forward_ms=0.0,
            scoring_ms=0.0,
        )
