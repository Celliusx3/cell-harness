"""Running a binary as a reaped subprocess with a timeout."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Completed:
    code: int
    stdout: bytes
    stderr: str


CommandRunner = Callable[[Sequence[str], float], Awaitable[Completed]]


async def run_command(argv: Sequence[str], timeout: float) -> Completed:
    """Run `argv` with no shell, ever."""
    process = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        async with asyncio.timeout(timeout):
            out, err = await process.communicate()
    except TimeoutError:
        process.kill()
        await process.wait()
        raise
    return Completed(
        code=process.returncode if process.returncode is not None else -1,
        stdout=out,
        stderr=err.decode("utf-8", "replace"),
    )
