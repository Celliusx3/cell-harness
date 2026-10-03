"""A multiple-choice question for the person, and the answer they tap."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

QUESTION_MAX_LENGTH = 240
OPTION_MAX_LENGTH = 80

Option = Annotated[str, Field(min_length=1, max_length=OPTION_MAX_LENGTH)]


class Question(BaseModel):
    """What `ask_user` is called with: one question and two to four distinct options."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    question: str = Field(min_length=1, max_length=QUESTION_MAX_LENGTH)
    options: tuple[Option, ...] = Field(min_length=2, max_length=4)

    @field_validator("options")
    @classmethod
    def _distinct(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("options must be distinct: the answer names a label, not a position")
        return value


class Answer(BaseModel):
    """The label the person chose — taken as sent, offered or not."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    choice: str = Field(min_length=1)
