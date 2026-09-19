"""Where media lives on disk."""

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
    """Whether a previous `fetch_reels` left anything to read."""
    directory = directory_for(root, shortcode)
    return directory.is_dir() and any(directory.iterdir())


def video_in(root: Path, shortcode: str) -> Path | None:
    return _first(directory_for(root, shortcode), "video.mp4")


_DURATION = "duration.txt"


def remember_duration(root: Path, shortcode: str, seconds: float | None) -> None:
    if seconds is None:
        return
    directory = directory_for(root, shortcode)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / _DURATION).write_text(f"{seconds}", encoding="utf-8")


def recall_duration(root: Path, shortcode: str) -> float | None:
    path = directory_for(root, shortcode) / _DURATION
    if not path.is_file():
        return None
    try:
        return float(path.read_text(encoding="utf-8").strip())
    except ValueError:
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
    """Delete reel directories last touched before the cutoff; return the count."""
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
