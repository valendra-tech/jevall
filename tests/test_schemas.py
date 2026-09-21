import pytest
from pydantic import ValidationError

from jev_gate.schemas import (
    ChoiceQuestion,
    DecisionRequest,
    ImagePart,
    NoulQuestion,
    ScoreQuestion,
    TextPart,
    VideoPart,
    normalize_state,
)


def choice_question(question_id: str = "team") -> ChoiceQuestion:
    return ChoiceQuestion(
        id=question_id,
        type="choice",
        prompt="Which team should handle this?",
        options=(
            {"id": "technical", "text": "Technical support"},
            {"id": "billing", "text": "Billing support"},
        ),
    )


def test_text_state_is_valid_and_normalizes_to_one_text_part():
    request = DecisionRequest(
        model="demo",
        state="A payment incident is under investigation.",
        questions=(choice_question(),),
    )

    assert request.state == "A payment incident is under investigation."
    assert normalize_state(request.state) == [
        TextPart(type="text", text="A payment incident is under investigation.")
    ]


def test_multimodal_state_preserves_native_content_parts():
    state = [
        TextPart(type="text", text="Review this checkout incident."),
        ImagePart(type="image", uri="file:///tmp/screenshot.png"),
        VideoPart(type="video", uri="file:///tmp/checkout.mp4"),
    ]

    assert normalize_state(state) == state


def test_request_supports_choice_score_and_noul_questions():
    request = DecisionRequest(
        model="demo",
        state="state",
        questions=(
            choice_question(),
            ScoreQuestion(
                id="severity",
                type="score",
                prompt="What is the severity?",
                levels=("low", "high"),
            ),
            NoulQuestion(
                id="refund",
                type="noul",
                prompt="Did the customer request a refund?",
            ),
        ),
    )

    assert [question.type for question in request.questions] == [
        "choice",
        "score",
        "noul",
    ]


def test_duplicate_question_and_option_ids_are_rejected():
    with pytest.raises(ValidationError, match="question IDs must be unique"):
        DecisionRequest(
            model="demo",
            state="state",
            questions=(choice_question("same"), choice_question("same")),
        )

    with pytest.raises(ValidationError, match="option IDs must be unique"):
        ChoiceQuestion(
            id="team",
            type="choice",
            prompt="Choose a team.",
            options=(
                {"id": "same", "text": "Technical"},
                {"id": "same", "text": "Billing"},
            ),
        )


def test_choice_and_score_questions_require_two_to_five_candidates():
    with pytest.raises(ValidationError, match="2 to 5"):
        ChoiceQuestion(
            id="team",
            type="choice",
            prompt="Choose a team.",
            options=({"id": "only", "text": "Only option"},),
        )

    with pytest.raises(ValidationError, match="2 to 5"):
        ScoreQuestion(
            id="severity",
            type="score",
            prompt="Choose a severity.",
            levels=("only",),
        )
