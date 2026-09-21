"""Protocol shared by local and remote model adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from jev_gate.schemas import DecisionRequest, DecisionResult, ModelInfo


@dataclass(frozen=True)
class AdapterBatch:
    """Decisions and timings produced by one adapter batch call."""

    decisions: tuple[tuple[DecisionResult, ...], ...]
    rows: int
    forward_ms: float
    scoring_ms: float


class DecisionAdapter(Protocol):
    """Backend contract consumed by the decision engine."""

    @property
    def model_info(self) -> ModelInfo:
        """Return stable model and capability metadata."""

    def decide(self, request: DecisionRequest) -> list[DecisionResult]:
        """Resolve each typed question in the request."""

    def decide_batch(
        self,
        requests: tuple[DecisionRequest, ...],
    ) -> AdapterBatch:
        """Resolve every request with one backend batch call."""
