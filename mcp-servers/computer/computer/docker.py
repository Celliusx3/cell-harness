"""The docker command line, behind a seam."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from computer.models.command import CommandResult
from computer.models.errors import EngineError, EngineTimeout


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
            raise EngineError(
                f"{self.executable} is not on PATH: install Docker and start it"
            ) from err
        try:
            async with asyncio.timeout(timeout_seconds):
                stdout, stderr = await process.communicate(stdin.encode())
        except TimeoutError as err:
            raise EngineTimeout(
                f"docker {args[0]} did not finish within {timeout_seconds:g} seconds"
            ) from err
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
        return CommandResult(
            returncode=await process.wait(), stdout=stdout.decode(), stderr=stderr.decode()
        )
