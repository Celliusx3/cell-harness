"""Running a binary, and the two rules that apply to every one we run.

Its own module rather than living beside the media seam, because **two
independent domains use it**: `media.sources` shells out to fetch, and
`read.frames` shells out to ffmpeg. Same shape as the harness's own
`sandbox/runner.py` — a seam that knows nothing about its callers.
"""

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
    """Run `argv` with no shell, ever.

    No `shell=True` and no string command: an argv list cannot be reinterpreted
    by a shell, and one of these arguments is a path derived from a
    model-supplied shortcode.
    """
    process = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        async with asyncio.timeout(timeout):
            out, err = await process.communicate()
    except TimeoutError:
        # We reap what we spawn — the harness invariant, and the reason a stuck
        # ffmpeg cannot outlive the call that started it.
        process.kill()
        await process.wait()
        raise
    return Completed(
        code=process.returncode if process.returncode is not None else -1,
        stdout=out,
        stderr=err.decode("utf-8", "replace"),
    )
