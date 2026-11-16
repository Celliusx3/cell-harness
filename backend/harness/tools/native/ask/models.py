"""What the ask tools are called with, and what they return."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from harness.llm import Usage
from harness.tools.native.ask import _descriptions

MAX_ASKED_FILES = 12


class AskModelArgs(BaseModel):
    """What the model passes to `ask_model`."""

    model_config = ConfigDict(frozen=True)

    paths: list[str] = Field(
        default_factory=list, max_length=MAX_ASKED_FILES, description=_descriptions.ASK_PATHS
    )
    instructions: str = Field(pattern=r"\S", description=_descriptions.ASK_INSTRUCTIONS)
    save_to: str | None = Field(default=None, description=_descriptions.ASK_SAVE_TO)


class AskModelJobsArgs(BaseModel):
    """What the model passes to `ask_model_jobs`."""

    model_config = ConfigDict(frozen=True)

    jobs_path: str = Field(description=_descriptions.JOBS_PATH)


class ModelJob(AskModelArgs):
    """One call a jobs file lists: `ask_model`'s arguments, with `save_to` required."""

    save_to: str = Field(description=_descriptions.ASK_SAVE_TO)


class ModelAnswer(BaseModel):
    """What `ask_model` returns to a script: the answer, where it was saved, and its tokens."""

    model_config = ConfigDict(frozen=True)

    answer: JsonValue
    saved_to: str | None
    usage: Usage | None


class JobFailure(BaseModel):
    """A job that was not answered: where its reply was to go, and why."""

    model_config = ConfigDict(frozen=True)

    save_to: str
    error: str


class JobsAnswered(BaseModel):
    """What `ask_model_jobs` returns: the jobs answered, those that were not, and their tokens."""

    model_config = ConfigDict(frozen=True)

    answered: int
    failed: list[JobFailure]
    usage: Usage
