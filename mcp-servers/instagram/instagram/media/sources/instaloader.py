"""The anonymous Instagram backend."""

from __future__ import annotations

import asyncio
import urllib.request
from pathlib import Path

from instagram.media import Media, RateLimited, Unavailable
from instagram.reel import ReelRef

NAME = "instaloader"

# Instagram's CDN serves media to anyone, but rejects a default urllib agent.
_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0"

# instaloader raises a few exception types for many causes, so the cause is matched on text.
_GONE = (
    "not exist",
    "unavailable",
    "not available",
    "private",
    "login_required",
    "checkpoint",
    "404",
)


class InstaloaderSource:
    """One reel at a time, anonymously, into a directory we own."""

    def __init__(self, *, timeout_seconds: float = 120.0) -> None:
        self._timeout = timeout_seconds

    @property
    def name(self) -> str:
        return NAME

    async def fetch(self, ref: ReelRef, into: Path) -> Media:
        return await asyncio.to_thread(self._fetch_blocking, ref, into)

    def _fetch_blocking(self, ref: ReelRef, into: Path) -> Media:
        import instaloader

        loader = instaloader.Instaloader(quiet=True, request_timeout=self._timeout)
        try:
            post = instaloader.Post.from_shortcode(loader.context, ref.shortcode)
        except Exception as err:
            raise _translate(err, ref) from err

        into.mkdir(parents=True, exist_ok=True)
        thumbnail = _download(post.url, into / "thumbnail.jpg", self._timeout)
        video = None
        if post.is_video and post.video_url:
            video = _download(post.video_url, into / "video.mp4", self._timeout)

        return Media(
            shortcode=ref.shortcode,
            video=video,
            thumbnail=thumbnail,
            caption=post.caption or "",
            author=post.owner_username or "",
            hashtags=tuple(post.caption_hashtags),
            mentions=tuple(post.caption_mentions),
            tagged_users=tuple(post.tagged_users),
            posted_at=post.date_utc,
            duration_seconds=post.video_duration,
            source=NAME,
        )


def _translate(err: Exception, ref: ReelRef) -> Exception:
    """One library exception to the one meaning the model can act on."""
    text = str(err)
    lowered = text.lower()

    if _looks_like_the_http1_429(text):
        return RateLimited(
            f"Instagram returned an immediate empty 429 for {ref.shortcode}. This is the known "
            "HTTP/1.1 rollout, not a real rate limit — waiting will not help; the fetch has to "
            "go over HTTP/2. Report it as a temporary Instagram-side problem.",
            retry_after_seconds=None,
        )
    if "429" in lowered or "too many requests" in lowered or "wait a few minutes" in lowered:
        return RateLimited(f"Instagram rate-limited the fetch of {ref.shortcode}: {text}")
    if any(marker in lowered for marker in _GONE):
        return Unavailable(
            f"Instagram would not serve {ref.shortcode}: the account is private, the post was "
            f"removed, or it is not publicly viewable ({text})"
        )
    return err


def _looks_like_the_http1_429(text: str) -> bool:
    """The empty-bodied 429 that fires on the first request of a fresh session."""
    lowered = text.lower()
    return "429" in lowered and ("empty" in lowered or "json" in lowered or lowered.count(" ") < 6)


def _download(url: str, target: Path, timeout: float) -> Path:
    request = urllib.request.Request(url, headers={"User-Agent": _AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        target.write_bytes(response.read())
    return target
