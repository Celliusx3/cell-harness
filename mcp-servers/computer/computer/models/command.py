"""What a program run in the PC gives back, whatever the engine."""

from __future__ import annotations

from dataclasses import dataclass

COMMAND_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def stdout_of(completed: CommandResult, action: str, *, error: type[Exception]) -> str:
    """`stdout`, or `error` saying what failed in the program's own words."""
    if completed.returncode != 0:
        said = completed.stderr.strip() or f"exit {completed.returncode}"
        raise error(f"{action} failed: {said}")
    return completed.stdout
