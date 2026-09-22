"""Execution shield for the Snake demo.

The shield never changes the model's distribution. It only decides whether the
raw top choice is executed or whether the highest-probability admissible
direction is executed instead, and it reports that intervention.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from jevall_snake.snake_features import DirectionFeatures, admissible_directions
from jevall_snake.snake_game import Direction


@dataclass(frozen=True)
class ShieldDecision:
    executed: Direction
    raw_choice: Direction
    shielded: bool
    reason: str


def top_direction(probabilities: Mapping[str, float]) -> Direction | None:
    """Highest-probability direction, preserving the model's own ordering."""
    best: Direction | None = None
    best_value = float("-inf")
    for direction in ("up", "down", "left", "right"):
        value = probabilities.get(direction)
        if value is None:
            continue
        if value > best_value:
            best, best_value = direction, value  # type: ignore[assignment]
    return best


def choose_execution(
    probabilities: Mapping[str, float],
    features: tuple[DirectionFeatures, ...],
    *,
    assisted: bool = True,
) -> ShieldDecision:
    """Execute the raw top choice, or the best admissible one when assisted."""
    raw_choice = top_direction(probabilities)
    if raw_choice is None:
        raise ValueError("the model returned no usable direction")

    if not assisted:
        return ShieldDecision(
            executed=raw_choice,
            raw_choice=raw_choice,
            shielded=False,
            reason="unassisted: the raw top choice is executed",
        )

    admissible = admissible_directions(features)
    if raw_choice in admissible:
        return ShieldDecision(
            executed=raw_choice,
            raw_choice=raw_choice,
            shielded=False,
            reason="the raw top choice is admissible",
        )

    if not admissible:
        return ShieldDecision(
            executed=raw_choice,
            raw_choice=raw_choice,
            shielded=False,
            reason="no admissible direction; the raw top choice is executed",
        )

    executed = max(
        admissible,
        key=lambda direction: probabilities.get(direction, 0.0),
    )
    return ShieldDecision(
        executed=executed,
        raw_choice=raw_choice,
        shielded=True,
        reason=(
            f"raw choice {raw_choice} is not admissible; "
            f"executed the best admissible direction {executed}"
        ),
    )
