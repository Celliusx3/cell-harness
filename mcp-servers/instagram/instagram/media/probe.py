"""Reading a video's duration off the file."""

from __future__ import annotations

from pathlib import Path

from instagram.command import CommandRunner


async def probe_duration(
    video: Path, *, ffprobe: str, run: CommandRunner, timeout_seconds: float
) -> float | None:
    """The video's duration in seconds, or None if it cannot be determined."""
    argv = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video),
    ]
    try:
        result = await run(argv, timeout_seconds)
    except (OSError, TimeoutError):
        return None
    if result.code != 0:
        return None
    try:
        seconds = float(result.stdout.decode("utf-8", "replace").strip())
    except ValueError:
        return None
    return seconds if seconds > 0 else None
