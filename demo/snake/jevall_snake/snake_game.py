"""Snake rules for the demo. Pure logic, no I/O and no model calls."""

from __future__ import annotations

from dataclasses import dataclass, replace
from random import Random
from typing import Literal

Direction = Literal["up", "down", "left", "right"]

DIRECTIONS: tuple[Direction, ...] = ("up", "down", "left", "right")

DELTAS: dict[Direction, tuple[int, int]] = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}

OPPOSITE: dict[Direction, Direction] = {
    "up": "down",
    "down": "up",
    "left": "right",
    "right": "left",
}

Outcome = Literal["moved", "ate", "wall", "self", "board-full"]


@dataclass(frozen=True)
class Point:
    x: int
    y: int


@dataclass(frozen=True)
class GameState:
    width: int
    height: int
    snake: tuple[Point, ...]  # head first
    direction: Direction
    food: Point
    score: int = 0
    moves: int = 0
    outcome: Outcome | None = None

    @property
    def head(self) -> Point:
        return self.snake[0]

    @property
    def length(self) -> int:
        return len(self.snake)

    def body(self, *, include_tail: bool = True) -> tuple[Point, ...]:
        segments = self.snake[1:]
        return segments if include_tail else segments[:-1]


def create_game(
    width: int = 12,
    height: int = 12,
    *,
    length: int = 3,
    seed: int | None = None,
) -> GameState:
    if width < 4 or height < 4:
        raise ValueError("board must be at least 4x4")
    if not 2 <= length <= width:
        raise ValueError("initial length must fit on the board")
    random = Random(seed)
    middle = height // 2
    start_x = min(width - 2, max(length - 1, width // 2))
    snake = tuple(Point(start_x - offset, middle) for offset in range(length))
    state = GameState(
        width=width,
        height=height,
        snake=snake,
        direction="right",
        food=Point(0, 0),
    )
    food = spawn_food(state, random)
    return replace(state, food=food if food is not None else Point(0, 0))


def spawn_food(state: GameState, random: Random) -> Point | None:
    occupied = {(point.x, point.y) for point in state.snake}
    free = [
        Point(x, y)
        for y in range(state.height)
        for x in range(state.width)
        if (x, y) not in occupied
    ]
    if not free:
        return None
    return free[random.randrange(len(free))]


def step(
    state: GameState, direction: Direction, random: Random | None = None
) -> GameState:
    """Apply exactly the requested direction. Fatal moves are not corrected."""
    random = random or Random()
    delta_x, delta_y = DELTAS[direction]
    head = state.head
    target = Point(head.x + delta_x, head.y + delta_y)
    moves = state.moves + 1

    if not (0 <= target.x < state.width and 0 <= target.y < state.height):
        return replace(state, direction=direction, moves=moves, outcome="wall")

    eats = target == state.food
    body = state.snake if eats else state.snake[:-1]
    if target in body:
        return replace(state, direction=direction, moves=moves, outcome="self")

    snake = (target, *body)
    if not eats:
        return replace(
            state,
            snake=snake,
            direction=direction,
            moves=moves,
            outcome="moved",
        )

    next_state = replace(
        state,
        snake=snake,
        direction=direction,
        moves=moves,
        score=state.score + 1,
    )
    food = spawn_food(next_state, random)
    if food is None:
        return replace(next_state, outcome="board-full")
    return replace(next_state, food=food, outcome="ate")


def is_fatal(outcome: Outcome | None) -> bool:
    return outcome in {"wall", "self", "board-full"}


def outcome_label(outcome: Outcome | None) -> str:
    return {
        "moved": "survived",
        "ate": "ate food",
        "wall": "WALL COLLISION",
        "self": "SELF COLLISION",
        "board-full": "BOARD FULL",
    }.get(outcome or "", "unknown")


def render_board(state: GameState) -> str:
    cells = [["." for _ in range(state.width)] for _ in range(state.height)]
    cells[state.food.y][state.food.x] = "F"
    for segment in state.snake[1:]:
        cells[segment.y][segment.x] = "S"
    cells[state.head.y][state.head.x] = "H"
    return "\n".join("".join(row) for row in cells)
