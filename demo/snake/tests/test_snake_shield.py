import pytest

from jevall_snake.snake import initial_state
from jevall_snake.snake_features import build_features, hamiltonian_cycle
from jevall_snake.snake_game import GameState, Point
from jevall_snake.snake_shield import choose_execution, top_direction


def game(**overrides) -> GameState:
    base = {
        "width": 6,
        "height": 6,
        "snake": (Point(3, 3), Point(2, 3), Point(1, 3)),
        "direction": "right",
        "food": Point(0, 0),
    }
    base.update(overrides)
    return GameState(**base)  # type: ignore[arg-type]


def test_top_direction_preserves_the_model_order():
    assert top_direction({"up": 0.2, "down": 0.5, "left": 0.1, "right": 0.2}) == "down"
    assert top_direction({"up": 0.5, "down": 0.5}) == "up"


def test_unassisted_executes_the_raw_choice_even_if_fatal():
    cycle = hamiltonian_cycle(6, 6)
    features = build_features(game(), cycle)

    decision = choose_execution({"right": 0.9, "up": 0.1}, features, assisted=False)

    assert decision.executed == "right"
    assert decision.shielded is False
    assert "unassisted" in decision.reason


def test_assisted_keeps_an_admissible_choice():
    state, cycle = initial_state(6, 6, 3, seed=1)
    features = build_features(state, cycle)
    admissible = [feature.direction for feature in features if feature.cycle_admissible]
    assert admissible

    decision = choose_execution({admissible[0]: 0.8}, features)

    assert decision.executed == admissible[0]
    assert decision.shielded is False


def test_assisted_replaces_a_fatal_choice_and_reports_it():
    cycle = hamiltonian_cycle(6, 6)
    # Head against the right wall: "right" is fatal and not admissible.
    wall_game = GameState(
        width=6,
        height=6,
        snake=(Point(5, 0), Point(4, 0), Point(3, 0)),
        direction="right",
        food=Point(0, 5),
    )
    features = build_features(wall_game, cycle)

    decision = choose_execution({"right": 0.9, "down": 0.1}, features)

    assert decision.raw_choice == "right"
    assert decision.shielded is True
    assert decision.executed != "right"
    assert "not admissible" in decision.reason


def test_no_admissible_direction_falls_back_to_the_raw_choice():
    cycle = hamiltonian_cycle(4, 4)
    trapped = GameState(
        width=4,
        height=4,
        snake=(Point(3, 3), Point(3, 2), Point(2, 2), Point(2, 3)),
        direction="right",
        food=Point(0, 0),
    )
    features = build_features(trapped, cycle)

    decision = choose_execution({"up": 0.6, "left": 0.4}, features)

    assert decision.executed == "up"
    assert "no admissible" in decision.reason


def test_missing_directions_raise():
    cycle = hamiltonian_cycle(4, 4)
    features = build_features(game(width=4, height=4), cycle)

    with pytest.raises(ValueError, match="no usable direction"):
        choose_execution({}, features)
