"""A bot's command as the shell tool returns it: still running, or done with its exit code."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

CommandStatus = Literal["done", "running"]


class CommandRun(BaseModel):
    """A bot's command: still running with its output so far, or done with its exit code."""

    model_config = ConfigDict(frozen=True)

    status: CommandStatus
    exit_code: int | None
    seconds: float
    output: str

    @model_validator(mode="after")
    def exit_code_fits_status(self) -> Self:
        if (self.status == "running") != (self.exit_code is None):
            raise ValueError("a running command has no exit code yet, and a done one has one")
        return self
