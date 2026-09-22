import pytest

from jevall_snake.snake import initial_state
from jevall_snake.snake_features import (
    admissible_directions,
    build_features,
    cycle_index,
    describe_features,
    forward_direction,
    hamiltonian_cycle,
    is_contiguous_arc,
    offered_features,
)
from jevall_snake.snake_game import DELTAS, GameState, Point


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_initial_state_keeps_the_food_free(seed):
    state, _ = initial_state(12, 12, 4, seed=seed)

    assert state.food not in state.snake


@pytest.mark.parametrize(
    "width,height",
    [(12, 12), (2, 6), (6, 2), (5, 6), (6, 5), (24, 16)],
)
def test_cycle_covers_every_cell_and_is_contiguous(width, height):
    cycle = hamiltonian_cycle(width, height)

    assert len(cycle) == width * height
    assert len(set(cycle)) == width * height
    for index, point in enumerate(cycle):
        nxt = cycle[(index + 1) % len(cycle)]
        distance = abs(point.x - nxt.x) + abs(point.y - nxt.y)
        assert distance == 1, f"{point} -> {nxt} is not adjacent"


def test_odd_by_odd_boards_have_no_cycle():
    with pytest.raises(ValueError, match="even dimension"):
        hamiltonian_cycle(5, 7)


def test_forward_direction_matches_the_cycle():
    cycle = hamiltonian_cycle(12, 12)
    point = cycle[0]
    nxt = cycle[1]

    direction = forward_direction(cycle, point)

    dx, dy = DELTAS[direction]
    assert (point.x + dx, point.y + dy) == (nxt.x, nxt.y)


def test_initial_state_follows_the_cycle():
    state, cycle = initial_state(12, 12, 3, seed=1)

    assert state.food not in state.snake
    assert is_contiguous_arc(cycle, state.snake)
    assert cycle_index(cycle)[(state.head.x, state.head.y)] >= 0
    assert admissible_directions(build_features(state, cycle))


def test_features_describe_every_legal_direction():
    state, cycle = initial_state(12, 12, 3, seed=1)
    features = build_features(state, cycle)

    assert len(features) == 4
    assert len(offered_features(features)) == 3
    offered = offered_features(features)
    assert all(feature.direction != "left" for feature in offered)
    assert all(feature.legal for feature in offered)


def test_features_flag_the_wall_and_the_cycle_step():
    game = GameState(
        width=6,
        height=6,
        snake=(Point(5, 0), Point(4, 0), Point(3, 0)),
        direction="right",
        food=Point(0, 5),
    )
    cycle = hamiltonian_cycle(6, 6)
    features = {feature.direction: feature for feature in build_features(game, cycle)}

    assert features["right"].hits_wall is True
    assert features["right"].open_cells == 0
    assert features["right"].cycle_step is None
    assert features["right"].cycle_admissible is False
    assert features["down"].cycle_step == 1
    assert features["down"].cycle_admissible is True


def test_features_report_space_for_dead_end_checks():
    game = GameState(
        width=5,
        height=6,
        snake=(Point(0, 0), Point(1, 0), Point(2, 0), Point(3, 0), Point(4, 0)),
        direction="right",
        food=Point(4, 5),
    )
    cycle = hamiltonian_cycle(5, 6)
    features = {feature.direction: feature for feature in build_features(game, cycle)}

    # 30 cells minus the 5 occupied plus the departing tail
    assert features["down"].open_cells == 26
    assert features["down"].fits is True


def test_describe_features_is_text_only():
    state, cycle = initial_state(8, 8, 3, seed=3)
    text = describe_features(build_features(state, cycle))

    assert "Planner features" in text
    assert "cycle_step" in text
    assert "reverse" in text
