from random import Random

import pytest

from jevall_snake.snake_game import (
    GameState,
    Point,
    create_game,
    is_fatal,
    outcome_label,
    render_board,
    step,
)


def state(**overrides) -> GameState:
    base = {
        "width": 6,
        "height": 6,
        "snake": (Point(2, 2), Point(1, 2), Point(0, 2)),
        "direction": "right",
        "food": Point(5, 0),
    }
    base.update(overrides)
    return GameState(**base)  # type: ignore[arg-type]


def test_create_game_places_the_snake_and_food():
    game = create_game(12, 12, length=3, seed=1)

    assert game.length == 3
    assert game.direction == "right"
    assert game.food not in game.snake
    assert game.outcome is None


def test_create_game_rejects_tiny_boards():
    with pytest.raises(ValueError, match="4x4"):
        create_game(3, 3)


def test_step_moves_and_drops_the_tail():
    moved = step(state(), "right", Random(0))

    assert moved.outcome == "moved"
    assert moved.head == Point(3, 2)
    assert moved.length == 3
    assert moved.moves == 1


def test_step_reports_wall_and_keeps_the_fatal_direction():
    game = state(snake=(Point(2, 0), Point(1, 0), Point(0, 0)))

    fatal = step(game, "up", Random(0))

    assert fatal.outcome == "wall"
    assert fatal.direction == "up"
    assert is_fatal(fatal.outcome)
    assert outcome_label(fatal.outcome) == "WALL COLLISION"


def test_step_reports_self_collision():
    game = state(
        snake=(
            Point(2, 2),
            Point(2, 1),
            Point(1, 1),
            Point(1, 2),
            Point(1, 3),
        ),
        direction="up",
    )

    assert step(game, "left", Random(0)).outcome == "self"


def test_step_allows_moving_into_the_departing_tail():
    game = state(
        snake=(Point(2, 2), Point(2, 1), Point(1, 1), Point(1, 2)),
        direction="down",
    )

    moved = step(game, "left", Random(0))

    assert moved.outcome == "moved"
    assert moved.head == Point(1, 2)


def test_step_grows_and_scores_when_eating():
    game = state(food=Point(3, 2))

    ate = step(game, "right", Random(0))

    assert ate.outcome == "ate"
    assert ate.length == 4
    assert ate.score == 1
    assert ate.food not in ate.snake


def test_render_board_marks_head_body_and_food():
    board = render_board(state(food=Point(3, 2))).splitlines()

    assert len(board) == 6
    assert all(len(row) == 6 for row in board)
    assert board[2] == "SSHF.."
