"""Deterministic planner features for the Snake demo.

The planner describes the board; it never chooses the move. The model receives
these descriptions and returns a distribution over directions.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from jevall_snake.snake_game import (
    DELTAS,
    OPPOSITE,
    Direction,
    GameState,
    Point,
)


def hamiltonian_cycle(width: int, height: int) -> tuple[Point, ...]:
    """Return a Hamiltonian cycle over the whole board (comb pattern).

    Row 0 runs left to right, rows 1..height-2 zig-zag between column 1 and the
    last column, the last row reaches column 0, and column 0 returns upward.
    An odd x odd grid has no Hamiltonian cycle, so at least one dimension must
    be even; for odd height the construction is transposed.
    """
    if width < 2 or height < 2:
        raise ValueError("cycle requires a board of at least 2x2")
    if width % 2 and height % 2:
        raise ValueError("a Hamiltonian cycle needs at least one even dimension")
    if height % 2:
        # Transpose the comb so the even dimension is the height.
        transposed = hamiltonian_cycle(height, width)
        return tuple(Point(point.y, point.x) for point in transposed)

    path: list[Point] = [Point(0, 0)]
    for x in range(1, width):
        path.append(Point(x, 0))
    for row in range(1, height - 1):
        columns = range(width - 1, 0, -1) if row % 2 else range(1, width)
        for x in columns:
            path.append(Point(x, row))
    last_row = height - 1
    for x in range(width - 1, -1, -1):
        path.append(Point(x, last_row))
    for row in range(height - 2, 0, -1):
        path.append(Point(0, row))

    if len(path) != width * height or len(set(path)) != width * height:
        raise AssertionError("cycle does not cover the board")
    return tuple(path)


def cycle_index(cycle: tuple[Point, ...]) -> dict[tuple[int, int], int]:
    return {(point.x, point.y): index for index, point in enumerate(cycle)}


def forward_direction(cycle: tuple[Point, ...], point: Point) -> Direction:
    """Direction the cycle travels when leaving `point`."""
    index = cycle_index(cycle)[(point.x, point.y)]
    nxt = cycle[(index + 1) % len(cycle)]
    for direction, (dx, dy) in DELTAS.items():
        if point.x + dx == nxt.x and point.y + dy == nxt.y:
            return direction
    raise AssertionError("cycle is not contiguous")


def is_contiguous_arc(cycle: tuple[Point, ...], snake: tuple[Point, ...]) -> bool:
    """True when the snake occupies consecutive cells of the cycle."""
    if len(snake) > len(cycle):
        return False
    lookup = cycle_index(cycle)
    indices = [lookup[(point.x, point.y)] for point in snake]
    total = len(cycle)
    return all(
        (indices[index] - indices[index + 1]) % total == 1
        for index in range(len(indices) - 1)
    )


@dataclass(frozen=True)
class DirectionFeatures:
    direction: Direction
    legal: bool
    target: Point
    hits_wall: bool
    hits_body: bool
    eats_food: bool
    food_distance_before: int
    food_distance_after: int
    open_cells: int
    fits: bool
    cycle_step: int | None
    cycle_admissible: bool

    @property
    def safe(self) -> bool:
        return not self.hits_wall and not self.hits_body and self.fits

    @property
    def food_progress(self) -> bool:
        return self.food_distance_after < self.food_distance_before


def _manhattan(left: Point, right: Point) -> int:
    return abs(left.x - right.x) + abs(left.y - right.y)


def _reachable_free_cells(
    state: GameState, start: Point, blocked: set[tuple[int, int]]
) -> int:
    if not (0 <= start.x < state.width and 0 <= start.y < state.height):
        return 0
    seen = {(start.x, start.y)}
    queue = deque([start])
    while queue:
        point = queue.popleft()
        for dx, dy in DELTAS.values():
            neighbour = Point(point.x + dx, point.y + dy)
            key = (neighbour.x, neighbour.y)
            if key in seen or key in blocked:
                continue
            if not (0 <= neighbour.x < state.width and 0 <= neighbour.y < state.height):
                continue
            seen.add(key)
            queue.append(neighbour)
    return len(seen)


def build_features(
    state: GameState,
    cycle: tuple[Point, ...],
) -> tuple[DirectionFeatures, ...]:
    lookup = cycle_index(cycle)
    head_index = lookup[(state.head.x, state.head.y)]
    total = len(cycle)
    features: list[DirectionFeatures] = []

    for direction in DELTAS:
        dx, dy = DELTAS[direction]
        target = Point(state.head.x + dx, state.head.y + dy)
        legal = direction != OPPOSITE[state.direction]
        hits_wall = not (0 <= target.x < state.width and 0 <= target.y < state.height)
        eats_food = target == state.food
        body = state.snake if eats_food else state.snake[:-1]
        hits_body = target in body

        if hits_wall:
            open_cells = 0
            cycle_step = None
        else:
            blocked = {
                (point.x, point.y)
                for point in (state.snake if eats_food else state.snake[:-1])
            }
            blocked.discard((target.x, target.y))
            open_cells = _reachable_free_cells(state, target, blocked)
            cycle_step = (lookup[(target.x, target.y)] - head_index) % total
            if cycle_step > total // 2:
                cycle_step -= total

        features.append(
            DirectionFeatures(
                direction=direction,
                legal=legal,
                target=target,
                hits_wall=hits_wall,
                hits_body=hits_body,
                eats_food=eats_food,
                food_distance_before=_manhattan(state.head, state.food),
                food_distance_after=_manhattan(target, state.food),
                open_cells=open_cells,
                fits=open_cells >= state.length,
                cycle_step=cycle_step,
                cycle_admissible=(
                    legal and not hits_wall and not hits_body and cycle_step == 1
                ),
            )
        )
    return tuple(features)


def offered_features(
    features: tuple[DirectionFeatures, ...],
) -> tuple[DirectionFeatures, ...]:
    """Only the reversal is removed; every other direction stays on the table."""
    return tuple(feature for feature in features if feature.legal)


def admissible_directions(
    features: tuple[DirectionFeatures, ...],
) -> tuple[Direction, ...]:
    return tuple(
        feature.direction
        for feature in features
        if feature.legal and feature.cycle_admissible
    )


def describe_features(features: tuple[DirectionFeatures, ...]) -> str:
    """Text block handed to the model. It describes, it does not decide."""
    lines = [
        "Planner features (deterministic, computed from the board):",
        "cycle_step = steps along the fixed safe cycle to the target cell;",
        "1 means the target is the next cycle cell.",
        "open_cells = empty cells reachable from the target after the move.",
        "fits = the snake still fits in that space.",
    ]
    for feature in features:
        if not feature.legal:
            lines.append(
                f"{feature.direction}: not offered (it would reverse the heading)."
            )
            continue
        target = f"({feature.target.x},{feature.target.y})"
        parts = [
            f"target {target}",
            "wall" if feature.hits_wall else "inside",
            "body" if feature.hits_body else "no body",
            "food" if feature.eats_food else "no food",
            f"open_cells {feature.open_cells}",
            f"fits {str(feature.fits).lower()}",
            f"cycle_step {feature.cycle_step}",
        ]
        lines.append(f"{feature.direction}: " + ", ".join(parts))
    return "\n".join(lines)
