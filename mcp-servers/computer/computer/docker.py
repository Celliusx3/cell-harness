"""The docker command line, behind a seam."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

COMMAND_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class DockerError(RuntimeError):
    """docker refused, or could not be run. The message says which, in docker's words."""


class DockerTimeout(DockerError):
    """docker did not answer in time and was killed."""


class Docker(Protocol):
    async def run(
        self, args: Sequence[str], *, stdin: str, timeout_seconds: float
    ) -> CommandResult:
        """Run `docker <args>` with `stdin`; a non-zero exit is returned, not raised."""


@dataclass(frozen=True)
class DockerCli:
    executable: str

    async def run(
        self, args: Sequence[str], *, stdin: str, timeout_seconds: float
    ) -> CommandResult:
        try:
            process = await asyncio.create_subprocess_exec(
                self.executable,
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as err:
            raise DockerError(
                f"{self.executable} is not on PATH: install Docker and start it"
            ) from err
        try:
            async with asyncio.timeout(timeout_seconds):
                stdout, stderr = await process.communicate(stdin.encode())
        except TimeoutError as err:
            raise DockerTimeout(
                f"docker {args[0]} did not finish within {timeout_seconds:g} seconds"
            ) from err
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
        return CommandResult(
            returncode=await process.wait(), stdout=stdout.decode(), stderr=stderr.decode()
        )


def stdout_of(completed: CommandResult, action: str) -> str:
    """`stdout`, or a `DockerError` in docker's own words."""
    if completed.returncode != 0:
        said = completed.stderr.strip() or f"exit {completed.returncode}"
        raise DockerError(f"{action} failed: {said}")
    return completed.stdout
