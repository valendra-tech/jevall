"""Terminal Snake demo driven by the jevall gateway.

The planner describes the board; the model returns a distribution over
directions; the shield decides whether to execute the raw top choice or the
best admissible one. See `README.md` for the modes.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import select
import statistics
import sys
import termios
import time
import tty
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from jevall_snake.snake_client import (
    DEFAULT_MODEL,
    DEFAULT_URL,
    DemoError,
    GatewayClient,
    Prediction,
)
from jevall_snake.snake_features import (
    DirectionFeatures,
    build_features,
    cycle_index,
    forward_direction,
    hamiltonian_cycle,
    is_contiguous_arc,
)
from jevall_snake.snake_game import (
    DELTAS,
    GameState,
    Point,
    create_game,
    is_fatal,
    outcome_label,
    spawn_food,
    step,
)
from jevall_snake.snake_shield import ShieldDecision, choose_execution


def initial_state(
    width: int,
    height: int,
    length: int,
    seed: int | None,
) -> tuple[GameState, tuple[Point, ...]]:
    """Start on the safe cycle: heading forward along it, body behind the head."""
    cycle = hamiltonian_cycle(width, height)
    base = create_game(width, height, length=length, seed=seed)
    heading = forward_direction(cycle, base.head)
    dx, dy = DELTAS[heading]
    body = tuple(
        Point(base.head.x - dx * offset, base.head.y - dy * offset)
        for offset in range(1, length)
    )
    snake = (base.head, *body)
    if not is_contiguous_arc(cycle, snake):
        raise DemoError("initial snake does not follow the safe cycle")
    state = GameState(
        width=base.width,
        height=base.height,
        snake=snake,
        direction=heading,
        food=base.food,
    )
    # Rebuilding the snake can cover the food: respawn it on a free cell.
    random_source = random.Random(seed)
    food = spawn_food(state, random_source)
    if food is None:
        raise DemoError("board has no free cell for food")
    state = GameState(
        width=state.width,
        height=state.height,
        snake=state.snake,
        direction=state.direction,
        food=food,
    )
    if (state.head.x, state.head.y) not in cycle_index(cycle):
        raise DemoError("initial head is off the cycle")
    return state, cycle


def board_text(state: GameState) -> str:
    return "\n".join(
        "".join(
            "H"
            if (x, y) == (state.head.x, state.head.y)
            else "S"
            if any((segment.x, segment.y) == (x, y) for segment in state.snake[1:])
            else "F"
            if (x, y) == (state.food.x, state.food.y)
            else "."
            for x in range(state.width)
        )
        for y in range(state.height)
    )


def feature_record(feature: DirectionFeatures) -> dict[str, Any]:
    return {
        "direction": feature.direction,
        "legal": feature.legal,
        "target": [feature.target.x, feature.target.y],
        "hits_wall": feature.hits_wall,
        "hits_body": feature.hits_body,
        "eats_food": feature.eats_food,
        "open_cells": feature.open_cells,
        "fits": feature.fits,
        "safe": feature.safe,
        "food_distance_before": feature.food_distance_before,
        "food_distance_after": feature.food_distance_after,
        "food_progress": feature.food_progress,
        "cycle_step": feature.cycle_step,
        "cycle_admissible": feature.cycle_admissible,
    }


def turn_record(
    state: GameState,
    features: tuple[DirectionFeatures, ...],
    prediction: Prediction,
    decision: ShieldDecision,
    next_state: GameState,
    *,
    assisted: bool,
) -> dict[str, Any]:
    return {
        "type": "turn",
        "turn": state.moves + 1,
        "board_before": board_text(state),
        "board_after": board_text(next_state),
        "head": [state.head.x, state.head.y],
        "food": [state.food.x, state.food.y],
        "direction": state.direction,
        "length": state.length,
        "score": state.score,
        "features": [feature_record(feature) for feature in features],
        "probabilities": prediction.probabilities,
        "dead_end_risk": prediction.dead_end_risk,
        "food_reachable": prediction.food_reachable,
        "raw_choice": decision.raw_choice,
        "executed": decision.executed,
        "shielded": decision.shielded,
        "shield_reason": decision.reason,
        "assisted": assisted,
        "latency_ms": prediction.latency_ms,
        "outcome": next_state.outcome,
        "timestamp": time.time(),
    }


class Recorder:
    def __init__(self, path: Path | None) -> None:
        self.path = path
        self.handle = None
        if path is not None:
            if path.exists():
                raise DemoError(f"recording already exists: {path}")
            path.parent.mkdir(parents=True, exist_ok=True)
            self.handle = path.open("w", encoding="utf-8")

    def write(self, record: dict[str, Any]) -> None:
        if self.handle is not None:
            self.handle.write(json.dumps(record) + "\n")
            self.handle.flush()

    def close(self) -> None:
        if self.handle is not None:
            self.handle.close()
            self.handle = None


class KeyReader:
    """Non-blocking single-key reader in cbreak mode, when stdin is a TTY."""

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled and sys.stdin.isatty()
        self._settings = None

    def __enter__(self) -> KeyReader:
        if self.enabled:
            self._settings = termios.tcgetattr(sys.stdin.fileno())
            tty.setcbreak(sys.stdin.fileno())
        return self

    def __exit__(self, *_: object) -> None:
        if self.enabled and self._settings is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._settings)

    def read(self) -> str | None:
        if not self.enabled:
            return None
        ready, _, _ = select.select([sys.stdin], [], [], 0)
        if not ready:
            return None
        return sys.stdin.read(1)


class Session:
    """One game, one decision at a time, with an optional recording."""

    def __init__(self, args: argparse.Namespace, recorder: Recorder) -> None:
        self.args = args
        self.recorder = recorder
        self.client = GatewayClient(
            url=args.url, model=args.model, timeout=args.timeout
        )
        self.assisted = not args.unassisted
        self.state, self.cycle = initial_state(
            args.width, args.height, args.initial_length, args.seed
        )
        self.random = random.Random(args.seed)
        self.executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="jevall-snake"
        )
        self.latencies: list[float] = []
        self.interventions = 0
        self.pending = None
        self.frame: Any = None
        self.error: str | None = None

    def restart(self) -> None:
        self.state, self.cycle = initial_state(
            self.args.width,
            self.args.height,
            self.args.initial_length,
            self.random.randrange(1 << 30),
        )
        self.interventions = 0
        self.latencies.clear()
        self.frame = None

    def submit(self) -> None:
        self.pending = self.executor.submit(self._run_turn)

    def _run_turn(self) -> None:
        state = self.state
        features = build_features(state, self.cycle)
        prediction = self.client.predict(state, features)
        decision = choose_execution(
            prediction.probabilities, features, assisted=self.assisted
        )
        self.latencies.append(prediction.latency_ms)
        if decision.shielded:
            self.interventions += 1
        next_state = step(state, decision.executed, self.random)
        self.recorder.write(
            turn_record(
                state,
                features,
                prediction,
                decision,
                next_state,
                assisted=self.assisted,
            )
        )
        self.state = next_state
        self.frame = (prediction, decision)

    def collect(self) -> None:
        assert self.pending is not None
        self.pending.result()
        self.pending = None

    @property
    def finished(self) -> bool:
        return is_fatal(self.state.outcome)

    @property
    def decision_rate(self) -> float:
        if not self.latencies:
            return 0.0
        recent = self.latencies[-10:]
        return 1000.0 / max(statistics.fmean(recent), 1e-6)

    def close(self) -> None:
        if self.pending is not None:
            self.pending.cancel()
        self.executor.shutdown(wait=False, cancel_futures=True)


def play(args: argparse.Namespace) -> int:
    from rich.console import Console
    from rich.live import Live

    from jevall_snake import snake_tui as tui

    console = Console()
    recorder = Recorder(Path(args.record) if args.record else None)
    session = Session(args, recorder)
    target_rate = args.fps
    best_score = 0
    paused = False
    started_at = time.monotonic()
    last_turn_at = started_at
    key_reader = KeyReader(enabled=not args.headless)
    exit_code = 0

    def frame_for(status: str) -> tui.Frame:
        prediction = session.frame[0] if session.frame else None
        decision = session.frame[1] if session.frame else None
        return tui.Frame(
            state=session.state,
            probabilities=prediction.probabilities if prediction else {},
            executed=decision.executed if decision else None,
            raw_choice=decision.raw_choice if decision else None,
            shielded=decision.shielded if decision else False,
            dead_end_risk=prediction.dead_end_risk if prediction else None,
            food_reachable=prediction.food_reachable if prediction else None,
            latency_ms=session.latencies[-1] if session.latencies else 0.0,
            decision_rate=session.decision_rate,
            assisted=session.assisted,
            interventions=session.interventions,
            best_score=best_score,
            status=status,
            reason=decision.reason if decision else "",
            model=args.model,
        )

    with key_reader:
        live = None
        if not args.headless:
            live = Live(console=console, refresh_per_second=12)
            live.__enter__()
        try:
            while True:
                key = key_reader.read()
                if key is not None:
                    if key in {"q", "Q", "\x03"}:
                        break
                    if key == " ":
                        paused = not paused
                    elif key in {"r", "R"}:
                        best_score = max(best_score, session.state.score)
                        session.restart()
                    elif key in {"+", "="}:
                        target_rate = min(target_rate + 2, 60)
                    elif key in {"-", "_"}:
                        target_rate = max(target_rate - 2, 1)

                if live is not None:
                    status = (
                        "game over"
                        if session.finished
                        else "thinking"
                        if session.pending is not None
                        else "paused"
                        if paused
                        else "running"
                    )
                    live.update(tui.render_frame(frame_for(status), console.width))

                if session.finished:
                    if live is not None:
                        live.update(tui.render_outcome(frame_for("game over")))
                    break

                if session.pending is None and not paused:
                    if not args.max_speed:
                        interval = 1.0 / max(target_rate, 0.1)
                        elapsed = time.monotonic() - last_turn_at
                        if elapsed < interval:
                            time.sleep(interval - elapsed)
                    last_turn_at = time.monotonic()
                    session.submit()

                if session.pending is not None and session.pending.done():
                    try:
                        session.collect()
                    except DemoError as caught:
                        session.error = str(caught)
                        exit_code = 2
                        break
                    if args.steps is not None and session.state.moves >= args.steps:
                        break
                    if (
                        args.duration is not None
                        and time.monotonic() - started_at >= args.duration
                    ):
                        break

                time.sleep(0.01)
        finally:
            session.close()
            if live is not None:
                live.__exit__(None, None, None)

    summary = {
        "type": "summary",
        "score": session.state.score,
        "moves": session.state.moves,
        "length": session.state.length,
        "cause": session.state.outcome,
        "interventions": session.interventions,
        "assisted": session.assisted,
        "model": args.model,
        "url": args.url,
        "width": args.width,
        "height": args.height,
        "seed": args.seed,
        "mean_latency_ms": statistics.fmean(session.latencies)
        if session.latencies
        else None,
        "error": session.error,
    }
    recorder.write(summary)
    recorder.close()

    if session.error is not None:
        console.print(f"[red]Decision API unavailable[/red]\n{session.error}")
        return 2
    console.print(
        f"score {session.state.score} · moves {session.state.moves} · "
        f"cause {outcome_label(session.state.outcome)} · "
        f"interventions {session.interventions}"
    )
    return exit_code


def benchmark(args: argparse.Namespace) -> int:
    from rich.console import Console

    console = Console()
    client = GatewayClient(url=args.url, model=args.model, timeout=args.timeout)
    results: list[dict[str, Any]] = []
    for rate in args.rates:
        for seed in args.seeds:
            state, cycle = initial_state(
                args.width, args.height, args.initial_length, seed
            )
            random_source = random.Random(seed)
            latencies: list[float] = []
            interventions = 0
            within = 0
            interval = 1.0 / rate
            next_tick = time.monotonic()
            started = time.monotonic()
            steps = 0
            while steps < args.steps and not is_fatal(state.outcome):
                next_tick += interval
                sleep_for = next_tick - time.monotonic()
                if sleep_for > 0:
                    time.sleep(sleep_for)
                tick_started = time.monotonic()
                features = build_features(state, cycle)
                prediction = client.predict(state, features)
                decision = choose_execution(
                    prediction.probabilities, features, assisted=not args.unassisted
                )
                if decision.shielded:
                    interventions += 1
                latencies.append(prediction.latency_ms)
                state = step(state, decision.executed, random_source)
                steps += 1
                if time.monotonic() - tick_started <= interval:
                    within += 1
            elapsed = time.monotonic() - started
            results.append(
                {
                    "rate": rate,
                    "seed": seed,
                    "steps": steps,
                    "alive": not is_fatal(state.outcome),
                    "score": state.score,
                    "interventions": interventions,
                    "achieved_per_second": steps / elapsed if elapsed else None,
                    "mean_latency_ms": statistics.fmean(latencies)
                    if latencies
                    else None,
                    "within_budget": within / steps if steps else None,
                }
            )
            console.print(
                f"rate {rate:>4} seed {seed:<5} steps {steps:>4} "
                f"score {state.score:>3} alive {str(not is_fatal(state.outcome)):<5} "
                f"interventions {interventions:>3} "
                f"achieved {results[-1]['achieved_per_second']:.2f}/s "
                f"within-budget {results[-1]['within_budget'] * 100:.1f}%"
            )
    if args.output:
        path = Path(args.output)
        if path.exists():
            raise DemoError(f"output already exists: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        console.print(f"wrote {path}")
    return 0


def report(args: argparse.Namespace) -> int:
    from rich.console import Console

    console = Console()
    path = Path(args.recording)
    turns: list[dict[str, Any]] = []
    summary: dict[str, Any] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("type") == "turn":
            turns.append(record)
        elif record.get("type") == "summary":
            summary = record
    if not turns:
        console.print("[red]no turns in the recording[/red]")
        return 2

    latencies = [turn["latency_ms"] for turn in turns if turn.get("latency_ms")]
    shielded = [turn for turn in turns if turn.get("shielded")]
    eaten = [turn for turn in turns if turn.get("outcome") == "ate"]
    ordered = sorted(latencies)
    p95 = (
        ordered[min(len(ordered) - 1, int(len(ordered) * 0.95) - 1)]
        if ordered
        else None
    )

    lines = [
        f"turns         {len(turns)}",
        f"eaten         {len(eaten)}",
        f"shielded      {len(shielded)}",
        f"cause         {summary.get('cause') or turns[-1].get('outcome')}",
        f"score         {summary.get('score', len(eaten))}",
        f"model         {summary.get('model', 'unknown')}",
        f"assisted      {summary.get('assisted')}",
    ]
    if latencies:
        lines.append(f"mean latency  {statistics.fmean(latencies):.1f} ms")
    if p95 is not None:
        lines.append(f"p95 latency   {p95:.1f} ms")
    console.print("\n".join(lines))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jevall-snake",
        description="Terminal Snake driven by the jevall decision gateway.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="play",
        choices=["play", "benchmark", "report"],
    )
    parser.add_argument("recording", nargs="?", help="recording path for `report`")
    parser.add_argument("--url", default=os.getenv("JEVALL_URL", DEFAULT_URL))
    parser.add_argument("--model", default=os.getenv("JEVALL_MODEL", DEFAULT_MODEL))
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--width", type=int, default=12)
    parser.add_argument("--height", type=int, default=12)
    parser.add_argument("--initial-length", type=int, default=3)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--fps", type=float, default=6.0, help="paced target decisions/second"
    )
    parser.add_argument("--max-speed", action="store_true", help="no pacing delay")
    parser.add_argument(
        "--unassisted", action="store_true", help="execute the raw top choice"
    )
    parser.add_argument("--headless", action="store_true", help="no terminal display")
    parser.add_argument(
        "--steps", type=int, default=None, help="stop after N decisions"
    )
    parser.add_argument(
        "--duration", type=float, default=None, help="stop after N seconds"
    )
    parser.add_argument("--record", default=None, help="write a JSONL recording")
    parser.add_argument("--rates", default="6,12,20", help="benchmark rates")
    parser.add_argument("--seeds", default="1,2", help="benchmark seeds")
    parser.add_argument("--output", default=None, help="benchmark JSON output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "benchmark":
        args.rates = [float(rate) for rate in args.rates.split(",") if rate.strip()]
        args.seeds = [int(seed) for seed in args.seeds.split(",") if seed.strip()]
        return benchmark(args)
    if args.command == "report":
        if not args.recording:
            raise SystemExit("report needs a recording path")
        return report(args)
    return play(args)


if __name__ == "__main__":
    raise SystemExit(main())
