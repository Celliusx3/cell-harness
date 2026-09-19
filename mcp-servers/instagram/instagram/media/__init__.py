"""How media is acquired."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from instagram.config import Config
from instagram.reel import ReelRef


@dataclass(frozen=True)
class Media:
    """Everything one backend could get for one reel."""

    shortcode: str
    video: Path | None
    thumbnail: Path | None
    caption: str
    author: str
    hashtags: tuple[str, ...]
    mentions: tuple[str, ...]
    tagged_users: tuple[str, ...]
    posted_at: datetime | None
    duration_seconds: float | None
    source: str


class Unavailable(Exception):
    """Private, deleted, or refused. An item status, not a bug in us."""


class RateLimited(Exception):
    """Instagram asked us to slow down."""

    def __init__(self, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class MediaSource(Protocol):
    """One way to turn a `ReelRef` into `Media` on local disk."""

    @property
    def name(self) -> str:
        """The backend name reported on every result."""
        ...

    async def fetch(self, ref: ReelRef, into: Path) -> Media:
        """Download into `into`, or raise `Unavailable` / `RateLimited`."""
        ...


def source_for(config: Config) -> MediaSource:
    """The backend `config.media_backend` names."""
    from instagram.media.sources.fixture import LocalFixtureSource
    from instagram.media.sources.instaloader import InstaloaderSource

    match config.media_backend:
        case "instaloader":
            return InstaloaderSource(timeout_seconds=config.request_timeout_seconds)
        case "fixture":
            if config.fixture_root is None:
                raise ValueError("fixture backend selected with no INSTAGRAM_FIXTURE_ROOT")
            return LocalFixtureSource(config.fixture_root)
        case unknown:
            raise ValueError(f"no media backend named {unknown!r}")
