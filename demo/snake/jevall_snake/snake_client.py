"""Gateway client for the Snake demo."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from jevall_snake.snake_features import (
    DirectionFeatures,
    describe_features,
    offered_features,
)
from jevall_snake.snake_game import GameState, render_board

DEFAULT_MODEL = "Qwen/Qwen3.5-4B"
DEFAULT_URL = "http://127.0.0.1:8000/v1/decisions"

RULES = """You are the decision engine for a Snake game. Answer the questions about
the board below. The board is described both as ASCII art and as planner
features. The planner describes the board; it does not choose the move.

Rules:
- The snake advances one cell per move and cannot reverse direction.
- Hitting a wall or the snake body ends the game.
- Eating food grows the snake and adds one point.
- A fixed safe cycle covers every cell. cycle_step 1 means the target cell is the
  next cell of that cycle, which is the safest possible progress.
"""


class DemoError(RuntimeError):
    """Raised when the gateway cannot answer, so the demo can pause."""


@dataclass(frozen=True)
class Prediction:
    probabilities: dict[str, float]
    dead_end_risk: float | None
    food_reachable: float | None
    latency_ms: float
    raw: dict[str, Any] = field(default_factory=dict)


def build_state(state: GameState, features: tuple[DirectionFeatures, ...]) -> str:
    return "\n".join(
        [
            RULES,
            "",
            f"Board size: {state.width}x{state.height}",
            "Coordinates: x increases left-to-right, y increases top-to-bottom.",
            f"Current direction: {state.direction.upper()}",
            f"Snake length: {state.length}",
            f"Score: {state.score}",
            "",
            "Legend: . = empty, H = snake head, S = snake body, F = food",
            "",
            "Board:",
            "",
            render_board(state),
            "",
            f"Snake head: ({state.head.x},{state.head.y})",
            "Snake body: ["
            + ",".join(f"({point.x},{point.y})" for point in state.body())
            + "]",
            f"Food: ({state.food.x},{state.food.y})",
            "",
            describe_features(features),
        ]
    )


def build_payload(
    state: GameState,
    features: tuple[DirectionFeatures, ...],
    *,
    model: str,
) -> dict[str, Any]:
    offered = offered_features(features)
    return {
        "model": model,
        "state": build_state(state, features),
        "questions": [
            {
                "id": "move",
                "type": "choice",
                "prompt": "Which direction should the snake move next?",
                "options": [
                    {"id": feature.direction, "text": f"Move {feature.direction}"}
                    for feature in offered
                ],
            },
            {
                "id": "dead_end",
                "type": "noul",
                "prompt": (
                    "After the next move, would the snake be unable to fit in the "
                    "remaining reachable free space?"
                ),
            },
            {
                "id": "food_reachable",
                "type": "noul",
                "prompt": (
                    "From the cells next to the head, is the food reachable without "
                    "crossing the snake body?"
                ),
            },
        ],
    }


def _post_json(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            # Some proxies reject the default urllib user agent.
            "User-Agent": "jevall-snake/0.1",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as reply:
        body = reply.read(1_000_000)
    if len(body) >= 1_000_000:
        raise DemoError("gateway response exceeded the size limit")
    return json.loads(body)


@dataclass
class GatewayClient:
    """One decision request per move, with an injectable transport."""

    url: str = DEFAULT_URL
    model: str = DEFAULT_MODEL
    timeout: float = 60.0
    transport: Callable[[str, dict[str, Any], float], dict[str, Any]] = _post_json

    def predict(
        self,
        state: GameState,
        features: tuple[DirectionFeatures, ...],
    ) -> Prediction:
        payload = build_payload(state, features, model=self.model)
        started = time.perf_counter()
        try:
            response = self.transport(self.url, payload, self.timeout)
        except urllib.error.HTTPError as error:
            raise DemoError(f"gateway HTTP {error.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise DemoError("gateway connection failed or timed out") from None
        except ValueError:
            raise DemoError("gateway returned invalid JSON") from None
        latency_ms = (time.perf_counter() - started) * 1000.0

        decisions = {
            decision["id"]: decision
            for decision in response.get("decisions", [])
            if isinstance(decision, dict) and "id" in decision
        }
        move = decisions.get("move")
        if not move or not isinstance(move.get("selected"), str):
            raise DemoError("gateway returned no move decision")

        def noul_probability(question_id: str) -> float | None:
            decision = decisions.get(question_id)
            if not decision:
                return None
            probabilities = decision.get("probabilities")
            if isinstance(probabilities, dict):
                value = probabilities.get("true")
                if isinstance(value, (int, float)):
                    return float(value)
            selected = decision.get("selected")
            return 1.0 if selected is True else 0.0 if selected is False else None

        return Prediction(
            probabilities={
                str(key): float(value)
                for key, value in (move.get("probabilities") or {}).items()
                if isinstance(value, (int, float))
            },
            dead_end_risk=noul_probability("dead_end"),
            food_reachable=noul_probability("food_reachable"),
            latency_ms=latency_ms,
            raw=response,
        )
