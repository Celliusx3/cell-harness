"""What a program run in the PC gives back, and how reaching the PC fails, whatever the engine."""

from __future__ import annotations

from dataclasses import dataclass

COMMAND_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class EngineError(RuntimeError):
    """The engine refused, or could not be reached. The message says which, in its own words."""


class EngineTimeout(EngineError):
    """The engine did not answer in time."""


def stdout_of(completed: CommandResult, action: str) -> str:
    """`stdout`, or an `EngineError` in the engine's own words."""
    if completed.returncode != 0:
        said = completed.stderr.strip() or f"exit {completed.returncode}"
        raise EngineError(f"{action} failed: {said}")
    return completed.stdout
