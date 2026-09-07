"""How media is acquired — the one seam that exists because the answer changes.

Which mechanism can read a public Instagram post is the least stable fact in this
whole capability. Measured in one afternoon: `yt-dlp` fails without cookies,
`gallery-dl` needs cookies *and* its profile path is currently broken with them,
`instagrapi`'s public path benchmarks at 0/4, and `instaloader` works anonymously
today because it bootstraps its own CSRF token. That ranking will not hold.

So acquisition is a Protocol with one explicit, startup-validated implementation
behind it, and everything above it — the tools, the models, the reading — is
written against `Media` and never against Instagram. Swapping backend is one
class and one arm of `source_for`.

`source_for` is here rather than in `sources/` so that selecting a backend and
defining what a backend *is* live together — a caller needs one import, and the
list of valid names sits beside the Protocol it satisfies.

**Bytes are fetched eagerly, never stored as a URL.** Measured expiry on
Instagram's CDN is roughly 35 hours for a video and four days for a poster image
(the `oe` query parameter is a hex Unix timestamp). A stored URL is a handle that
silently stops resolving, which would present as "the reel vanished".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from instagram.config import Config
from instagram.reel import ReelRef


@dataclass(frozen=True)
class Media:
    """Everything one backend could get for one reel.

    `video is None` with `thumbnail` set is a real, supported outcome — an image
    post, or a video Instagram would not serve. Callers degrade rather than fail,
    because a caption plus a poster frame is still evidence.
    """

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
    """Instagram asked us to slow down.

    Carries `retry_after_seconds` when the backend could determine one, so the
    model can decide whether waiting is worth it rather than guessing.
    """

    def __init__(self, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class MediaSource(Protocol):
    """One way to turn a `ReelRef` into `Media` on local disk."""

    @property
    def name(self) -> str:
        """Reported back as `backend`, so a result says how it was obtained."""
        ...

    async def fetch(self, ref: ReelRef, into: Path) -> Media:
        """Download into `into`, or raise `Unavailable` / `RateLimited`."""
        ...


def source_for(config: Config) -> MediaSource:
    """The backend `config.media_backend` names.

    One dict-style lookup, raising on an unknown name. No fallback chain: a
    silent default is how you end up debugging Instagram when the fixture
    backend was selected. `config.load()` already rejected an unknown name at
    startup, so reaching the raise here means the two lists drifted.
    """
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
