"""What a program run in the PC gives back, whatever the engine."""

from __future__ import annotations

from dataclasses import dataclass

from computer.models.errors import EngineError

COMMAND_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def stdout_of(completed: CommandResult, action: str) -> str:
    """`stdout`, or an `EngineError` in the engine's own words."""
    if completed.returncode != 0:
        said = completed.stderr.strip() or f"exit {completed.returncode}"
        raise EngineError(f"{action} failed: {said}")
    return completed.stdout
