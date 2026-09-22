import pytest

from jevall_snake.snake_client import (
    DemoError,
    GatewayClient,
    build_payload,
    build_state,
)
from jevall_snake.snake_features import build_features, hamiltonian_cycle
from jevall_snake.snake_game import GameState, Point


def game() -> GameState:
    return GameState(
        width=6,
        height=6,
        snake=(Point(3, 3), Point(2, 3), Point(1, 3)),
        direction="right",
        food=Point(0, 0),
    )


def response(**overrides) -> dict:
    base = {
        "id": "dec_test",
        "model": "Qwen/Qwen3.5-4B",
        "decisions": [
            {
                "id": "move",
                "type": "choice",
                "selected": "up",
                "probabilities": {"up": 0.6, "down": 0.1, "right": 0.3},
            },
            {
                "id": "dead_end",
                "type": "noul",
                "selected": False,
                "probabilities": {"false": 0.8, "true": 0.2},
            },
            {
                "id": "food_reachable",
                "type": "noul",
                "selected": True,
                "probabilities": {"false": 0.1, "true": 0.9},
            },
        ],
        "usage": {"latency_ms": 42},
        "diagnostics": {"queue_ms": 8, "forward_ms": 30, "scoring_ms": 4},
    }
    base.update(overrides)
    return base


def test_payload_offers_three_directions_and_three_questions():
    state = game()
    features = build_features(state, hamiltonian_cycle(6, 6))

    payload = build_payload(state, features, model="Qwen/Qwen3.5-4B")

    assert [question["id"] for question in payload["questions"]] == [
        "move",
        "dead_end",
        "food_reachable",
    ]
    move = payload["questions"][0]
    assert {option["id"] for option in move["options"]} == {"up", "down", "right"}
    assert payload["model"] == "Qwen/Qwen3.5-4B"
    assert "Planner features" in payload["state"]


def test_state_includes_board_and_planner_features():
    state = game()
    features = build_features(state, hamiltonian_cycle(6, 6))

    text = build_state(state, features)

    assert "Board size: 6x6" in text
    assert "Current direction: RIGHT" in text
    assert "Snake head: (3,3)" in text
    assert "cycle_step" in text
    assert "H" in text and "S" in text and "F" in text


def test_predict_parses_choice_and_noul_probabilities():
    calls = []

    def transport(url, payload, timeout):
        calls.append((url, payload, timeout))
        return response()

    client = GatewayClient(url="http://example.test/v1/decisions", transport=transport)
    prediction = client.predict(game(), build_features(game(), hamiltonian_cycle(6, 6)))

    assert prediction.probabilities == {"up": 0.6, "down": 0.1, "right": 0.3}
    assert prediction.dead_end_risk == pytest.approx(0.2)
    assert prediction.food_reachable == pytest.approx(0.9)
    assert prediction.latency_ms >= 0
    assert calls[0][0] == "http://example.test/v1/decisions"
    assert calls[0][2] == client.timeout


def test_predict_reports_gateway_failures_as_demo_errors():
    def transport(url, payload, timeout):
        raise OSError("connection refused")

    client = GatewayClient(transport=transport)

    with pytest.raises(DemoError, match="connection failed"):
        client.predict(game(), build_features(game(), hamiltonian_cycle(6, 6)))


def test_predict_requires_a_move_decision():
    def transport(url, payload, timeout):
        return response(
            decisions=[{"id": "dead_end", "type": "noul", "selected": True}]
        )

    client = GatewayClient(transport=transport)

    with pytest.raises(DemoError, match="no move decision"):
        client.predict(game(), build_features(game(), hamiltonian_cycle(6, 6)))
