"""Terminal rendering for the Snake demo (Rich)."""

from __future__ import annotations

from dataclasses import dataclass

from rich.align import Align
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from jevall_snake.snake_game import DIRECTIONS, Direction, GameState, outcome_label

HEAD_STYLE = "bold green"
BODY_STYLE = "green"
FOOD_STYLE = "bold yellow"
EMPTY_STYLE = "grey27"
WALL_STYLE = "grey50"

MIN_COLUMNS = 88
MIN_ROWS = 28


@dataclass
class Frame:
    state: GameState
    probabilities: dict[str, float]
    executed: Direction | None
    raw_choice: Direction | None
    shielded: bool
    dead_end_risk: float | None
    food_reachable: float | None
    latency_ms: float
    decision_rate: float
    assisted: bool
    interventions: int
    best_score: int
    status: str
    reason: str
    model: str
    network: str = "local gateway"


def render_board(state: GameState) -> Text:
    text = Text()
    for y in range(state.height):
        for x in range(state.width):
            point = (x, y)
            if point == (state.head.x, state.head.y):
                text.append("██", style=HEAD_STYLE)
            elif any((segment.x, segment.y) == point for segment in state.snake[1:]):
                text.append("██", style=BODY_STYLE)
            elif point == (state.food.x, state.food.y):
                text.append("██", style=FOOD_STYLE)
            else:
                text.append("· ", style=EMPTY_STYLE)
        text.append("\n")
    return text


def probability_bars(
    probabilities: dict[str, float], executed: Direction | None
) -> Table:
    table = Table.grid(padding=(0, 1))
    table.add_column(justify="left")
    table.add_column(justify="left")
    table.add_column(justify="right")
    for direction in DIRECTIONS:
        if direction not in probabilities:
            continue
        value = probabilities[direction]
        filled = max(1, round(value * 12))
        bar = "█" * filled + "░" * (12 - filled)
        style = "bold green" if direction == executed else "grey62"
        table.add_row(
            direction.upper(),
            Text(bar, style=style),
            Text(f"{value * 100:5.1f}%", style=style),
        )
    return table


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def render_panel(frame: Frame) -> RenderableType:
    state = frame.state
    mode = "assisted (cycle shield)" if frame.assisted else "unassisted"
    header = Text()
    header.append("JEVALL SNAKE\n", style="bold white")
    header.append("one probabilistic decision per move\n", style="grey62")
    header.append(f"model {frame.model}\n", style="grey50")
    header.append(f"mode {mode} · {frame.network}", style="grey50")

    selected = Text()
    if frame.executed is not None:
        selected.append("\nEXECUTED ", style="grey62")
        selected.append(frame.executed.upper(), style="bold green")
    if frame.shielded:
        selected.append("  SHIELD", style="bold yellow")
        selected.append(
            f"\nraw choice {frame.raw_choice.upper() if frame.raw_choice else 'n/a'}",
            style="grey62",
        )

    stats = Table.grid(padding=(0, 1))
    stats.add_column(justify="left")
    stats.add_column(justify="right")
    stats.add_row("SCORE", f"{state.score}")
    stats.add_row("LENGTH", f"{state.length}")
    stats.add_row("MOVES", f"{state.moves}")
    stats.add_row("BEST", f"{frame.best_score}")
    stats.add_row("DEAD-END RISK", _percent(frame.dead_end_risk))
    stats.add_row("FOOD REACHABLE", _percent(frame.food_reachable))
    stats.add_row("INFERENCE", f"{frame.latency_ms:.0f} ms")
    stats.add_row("DECISIONS", f"{frame.decision_rate:.1f}/s")
    stats.add_row("INTERVENTIONS", f"{frame.interventions}")

    body = Group(
        header,
        Text("\n"),
        probability_bars(frame.probabilities, frame.executed),
        selected,
        Text("\n"),
        stats,
        Text(f"\nSTATUS {frame.status}", style="grey62"),
    )
    return Panel(body, border_style="grey35", padding=(1, 2))


def render_frame(frame: Frame, columns: int) -> RenderableType:
    board_width = frame.state.width * 2 + 6
    board_panel = Panel(
        Align.center(render_board(frame.state), vertical="middle"),
        border_style="grey35",
        padding=(1, 2),
    )
    layout = Table.grid(padding=(0, 2))
    if columns >= board_width + 46:
        layout.add_column()
        layout.add_column()
        layout.add_row(board_panel, render_panel(frame))
    else:
        layout.add_column()
        layout.add_row(board_panel)
        layout.add_row(render_panel(frame))

    footer = Text(
        "space pause · r restart · q quit · +/- speed",
        style="grey50",
    )
    return Group(layout, footer)


def render_outcome(frame: Frame) -> RenderableType:
    state = frame.state
    lines = [
        Text("GAME OVER", style="bold red"),
        Text(f"score {state.score} · moves {state.moves} · length {state.length}"),
        Text(f"cause {outcome_label(state.outcome)}"),
        Text(f"interventions {frame.interventions}"),
    ]
    if frame.raw_choice is not None:
        lines.append(Text(f"final raw choice {frame.raw_choice.upper()}"))
    return Panel(Group(*lines), border_style="red", padding=(1, 2))


def too_small(columns: int, rows: int) -> str | None:
    if columns < MIN_COLUMNS or rows < MIN_ROWS:
        return (
            f"terminal too small: need at least {MIN_COLUMNS}x{MIN_ROWS}, "
            f"have {columns}x{rows}"
        )
    return None
