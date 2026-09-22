"""Public Pydantic schemas for the Jev-compatible decision contract."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ContractModel(BaseModel):
    """Base model with a deliberately strict public contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def _nonblank(value: str, field_name: str) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} must not be blank")
    return value


class TextPart(ContractModel):
    type: Literal["text"]
    text: str = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _nonblank(value, "text")


class ImagePart(ContractModel):
    type: Literal["image"]
    uri: str = Field(min_length=1)

    @field_validator("uri")
    @classmethod
    def validate_uri(cls, value: str) -> str:
        return _nonblank(value, "uri")


class VideoPart(ContractModel):
    type: Literal["video"]
    uri: str = Field(min_length=1)

    @field_validator("uri")
    @classmethod
    def validate_uri(cls, value: str) -> str:
        return _nonblank(value, "uri")


ContentPart = Annotated[
    TextPart | ImagePart | VideoPart,
    Field(discriminator="type"),
]
State = str | list[ContentPart]


class Option(ContractModel):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)

    @field_validator("id", "text")
    @classmethod
    def validate_strings(cls, value: str, info) -> str:
        return _nonblank(value, info.field_name)


class ChoiceQuestion(ContractModel):
    id: str = Field(min_length=1)
    type: Literal["choice"]
    prompt: str = Field(min_length=1)
    options: tuple[Option, ...]

    @field_validator("id", "prompt")
    @classmethod
    def validate_strings(cls, value: str, info) -> str:
        return _nonblank(value, info.field_name)

    @model_validator(mode="after")
    def validate_options(self) -> ChoiceQuestion:
        if not 2 <= len(self.options) <= 5:
            raise ValueError("options must contain 2 to 5 items")
        option_ids = [option.id for option in self.options]
        if len(set(option_ids)) != len(option_ids):
            raise ValueError("option IDs must be unique")
        return self


class ScoreQuestion(ContractModel):
    id: str = Field(min_length=1)
    type: Literal["score"]
    prompt: str = Field(min_length=1)
    levels: tuple[str, ...]

    @field_validator("id", "prompt")
    @classmethod
    def validate_strings(cls, value: str, info) -> str:
        return _nonblank(value, info.field_name)

    @field_validator("levels")
    @classmethod
    def validate_levels(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not 2 <= len(value) <= 5:
            raise ValueError("levels must contain 2 to 5 items")
        if any(not level.strip() for level in value):
            raise ValueError("levels must not contain blank values")
        if len(set(value)) != len(value):
            raise ValueError("levels must be unique")
        return value


class NoulQuestion(ContractModel):
    id: str = Field(min_length=1)
    type: Literal["noul"]
    prompt: str = Field(min_length=1)

    @field_validator("id", "prompt")
    @classmethod
    def validate_strings(cls, value: str, info) -> str:
        return _nonblank(value, info.field_name)


Question = Annotated[
    ChoiceQuestion | ScoreQuestion | NoulQuestion,
    Field(discriminator="type"),
]


class DecisionRequest(ContractModel):
    model: str = Field(min_length=1)
    state: State
    questions: tuple[Question, ...]

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        return _nonblank(value, "model")

    @model_validator(mode="after")
    def validate_question_ids(self) -> DecisionRequest:
        if not self.questions:
            raise ValueError("questions must not be empty")
        question_ids = [question.id for question in self.questions]
        if len(set(question_ids)) != len(question_ids):
            raise ValueError("question IDs must be unique")
        return self

    def normalized_state(self) -> list[ContentPart]:
        return normalize_state(self.state)


def normalize_state(state: State) -> list[ContentPart]:
    """Normalize the string shorthand without changing native media parts."""
    if isinstance(state, str):
        return [TextPart(type="text", text=state)]
    return list(state)


class DecisionResult(ContractModel):
    id: str
    type: Literal["choice", "score", "noul"]
    selected: str | bool
    probabilities: dict[str, float] | None = None


class Usage(ContractModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: float


class DecisionResponse(ContractModel):
    id: str
    model: str
    decisions: tuple[DecisionResult, ...]
    usage: Usage
    diagnostics: dict[str, object]


class ModelInfo(ContractModel):
    id: str
    backend: str
    modalities: tuple[Literal["text", "image", "video"], ...]
    decision_types: tuple[Literal["choice", "score", "noul"], ...]


class ModelListResponse(ContractModel):
    data: tuple[ModelInfo, ...]


class HealthResponse(ContractModel):
    status: Literal["ok"]
    model: str | None = None
    device: str | None = None
    dtype: str | None = None
    ready: bool | None = None
