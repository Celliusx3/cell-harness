"""Reading a video's duration off the file.

In `media/` rather than `read/` because a duration is a fact about the media, not
an interpretation of it — and because `media.fetch` is the only caller. Putting
it beside the frame sampler made `media` import from `read`, which inverted the
dependency for one function.

Needed because **instaloader does not always report a duration** — observed live
on a real reel, where `video_duration` came back `None`. Without one, frames fall
back to a fixed interval and `sampled_over_seconds` reports 0, which is honest
but makes the even-spreading guarantee vacuous on exactly the long videos it
exists for.
"""

from __future__ import annotations

from pathlib import Path

from instagram.command import CommandRunner


async def probe_duration(
    video: Path, *, ffprobe: str, run: CommandRunner, timeout_seconds: float
) -> float | None:
    """The video's duration in seconds, or None if it cannot be determined.

    Needed because **instaloader does not always report one** — observed live on
    a real reel, where `video_duration` came back `None`. Without a duration,
    frames fall back to a fixed interval and `sampled_over_seconds` reports 0,
    which is honest but makes the even-spreading guarantee vacuous on exactly the
    long videos it exists for.

    Never raises: ffprobe missing or failing is a degraded read, not a failed
    one. Returning None keeps the fallback path intact.
    """
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
