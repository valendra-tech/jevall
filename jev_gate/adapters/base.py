"""Protocol shared by local and remote model adapters."""

from __future__ import annotations

from typing import Protocol

from jev_gate.schemas import DecisionRequest, DecisionResult, ModelInfo


class DecisionAdapter(Protocol):
    """Backend contract consumed by the decision engine."""

    @property
    def model_info(self) -> ModelInfo:
        """Return stable model and capability metadata."""

    def decide(self, request: DecisionRequest) -> list[DecisionResult]:
        """Resolve each typed question in the request."""
