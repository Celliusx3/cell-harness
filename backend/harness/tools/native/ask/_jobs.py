"""A jobs file: the `ask_model` calls it lists, read and checked before any is made."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import Field, TypeAdapter, ValidationError

from harness.tools.domain.outcome import INVALID_ARGUMENTS, Failure
from harness.tools.native.ask.models import ModelJob

MAX_JOBS = 500

JOBS = TypeAdapter(Annotated[list[ModelJob], Field(min_length=1, max_length=MAX_JOBS)])


def jobs_in(path: Path) -> list[ModelJob] | Failure:
    """The jobs `path` lists; a refusal naming what is wrong when it is not 1 to MAX_JOBS jobs."""
    try:
        return JOBS.validate_json(path.read_bytes())
    except (OSError, ValidationError) as err:
        reason = str(err).splitlines()[0]
        return Failure(
            INVALID_ARGUMENTS,
            f"{path} is not a list of 1 to {MAX_JOBS} jobs, each with instructions and "
            f"save_to: {reason}",
        )
