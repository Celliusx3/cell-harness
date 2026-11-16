"""A jobs file: the `ask_about_images` calls it lists, read and checked before any is made."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from harness.tools.domain.outcome import INVALID_ARGUMENTS, Failure
from harness.tools.native.files import _descriptions
from harness.tools.native.files.models import AskAboutImagesArgs

MAX_JOBS = 500


class ImageJob(AskAboutImagesArgs):
    """One call a jobs file lists: `ask_about_images`'s arguments, with `save_to` required."""

    save_to: str = Field(description=_descriptions.ASK_SAVE_TO)


JOBS = TypeAdapter(Annotated[list[ImageJob], Field(min_length=1, max_length=MAX_JOBS)])


class JobFailure(BaseModel):
    """A job that was not answered: where its reply was to go, and why."""

    model_config = ConfigDict(frozen=True)

    save_to: str
    error: str


class JobsAnswered(BaseModel):
    """What `ask_about_image_jobs` returns: how many jobs were answered, and those that were not."""

    model_config = ConfigDict(frozen=True)

    answered: int
    failed: list[JobFailure]


def jobs_in(path: Path) -> list[ImageJob] | Failure:
    """The jobs `path` lists; a refusal naming what is wrong when it is not 1 to MAX_JOBS jobs."""
    try:
        return JOBS.validate_json(path.read_bytes())
    except (OSError, ValidationError) as err:
        reason = str(err).splitlines()[0]
        return Failure(
            INVALID_ARGUMENTS,
            f"{path} is not a list of 1 to {MAX_JOBS} jobs, each with paths, instructions and "
            f"save_to: {reason}",
        )
