"""Where media lives, and why a shortcode can never escape it.

This is `whisper-mcp`'s "media-root boundary" reused. Everything downloaded goes
under one root, addressed by shortcode, and `directory_for` is the only function
that turns a shortcode into a path.

**The boundary is the regex, not a string check here.** A shortcode only ever
arrives via `reel.parse`, whose pattern is `[A-Za-z0-9_-]+` — no dot, no slash,
so `..` and absolute paths are unrepresentable. `directory_for` re-asserts it
anyway, because this function is one refactor away from being handed a raw
model-supplied string, and at that point the regex is somebody else's invariant.

`0700` on the root: media downloaded from someone's Instagram is not for other
users of the machine to read.
"""

from __future__ import annotations

import re
import shutil
import time
from pathlib import Path

_SAFE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class UnsafeShortcode(ValueError):
    """A shortcode that could leave the media root. Never expected; always fatal."""


def directory_for(root: Path, shortcode: str) -> Path:
    """`root/<shortcode>`, having proven the shortcode cannot traverse."""
    if not _SAFE.match(shortcode):
        raise UnsafeShortcode(f"{shortcode!r} is not a usable shortcode")
    root.mkdir(parents=True, exist_ok=True)
    root.chmod(0o700)
    return root / shortcode


def has_media(root: Path, shortcode: str) -> bool:
    """Whether a previous `fetch_reels` left anything to read.

    What makes `read_reels` able to answer `not_fetched` with a real instruction
    instead of a confusing empty result.
    """
    directory = directory_for(root, shortcode)
    return directory.is_dir() and any(directory.iterdir())


def video_in(root: Path, shortcode: str) -> Path | None:
    return _first(directory_for(root, shortcode), "video.mp4")


# `fetch_reels` knows the duration and `read_reels` needs it — to spread frames
# across the whole video and to report `sampled_over_seconds` truthfully. They
# are separate calls, so it is written down. The alternative was shelling out to
# ffprobe on every read, which is a second binary to require for a number we
# already had.
_DURATION = "duration.txt"


def remember_duration(root: Path, shortcode: str, seconds: float | None) -> None:
    if seconds is None:
        return
    directory = directory_for(root, shortcode)
    # `directory_for` creates the *root*, not the reel's own directory — in the
    # live flow the media backend does that when it downloads. This has to work
    # before any download too, so it creates it here rather than assuming.
    directory.mkdir(parents=True, exist_ok=True)
    (directory / _DURATION).write_text(f"{seconds}", encoding="utf-8")


def recall_duration(root: Path, shortcode: str) -> float | None:
    path = directory_for(root, shortcode) / _DURATION
    if not path.is_file():
        return None
    try:
        return float(path.read_text(encoding="utf-8").strip())
    except ValueError:
        # A corrupt sidecar must not fail the read: without it frames fall back
        # to a fixed interval and say so, which is strictly better than no read.
        return None


def thumbnail_in(root: Path, shortcode: str) -> Path | None:
    return _first(directory_for(root, shortcode), "thumbnail.jpg")


def forget(root: Path, shortcode: str) -> bool:
    """Drop one reel's media. True if there was anything to drop."""
    directory = directory_for(root, shortcode)
    if not directory.is_dir():
        return False
    shutil.rmtree(directory)
    return True


def sweep(root: Path, *, older_than_seconds: float, now: float | None = None) -> int:
    """Delete reel directories last touched before the cutoff; return the count.

    Called at startup rather than on a timer. A server that is not running
    accumulates nothing, and a timer would be a background task to own and cancel
    for a problem that a single sweep already solves.
    """
    if not root.is_dir():
        return 0
    cutoff = (time.time() if now is None else now) - older_than_seconds
    removed = 0
    for child in root.iterdir():
        if child.is_dir() and child.stat().st_mtime < cutoff:
            shutil.rmtree(child, ignore_errors=True)
            removed += 1
    return removed


def _first(directory: Path, name: str) -> Path | None:
    candidate = directory / name
    return candidate if candidate.is_file() else None
