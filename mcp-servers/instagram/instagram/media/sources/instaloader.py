"""The anonymous Instagram backend.

**Why instaloader and not yt-dlp.** Instagram serves a logged-out visitor a
620 KB JavaScript shell with *zero* meta tags — no caption, no thumbnail, not even
`og:title`, and the same shell for a post that does not exist. So the meta tags
every scraper used to read are injected client-side, and any raw-HTTP client must
talk to the private GraphQL endpoint instead. instaloader does, and — verified
against a live public reel — bootstraps its own CSRF token so it needs no
account. yt-dlp does not, and fails at metadata, webpage *and* embed.

**What is not available anonymously.** The location sticker, by explicit upstream
design (`Post.location` returns `None` when not logged in). We do not ask for it
and do not carry a field for it; `tagged_users` is the corroborating signal.

**The failure mode worth naming.** Instagram answers HTTP/1.1 web-API requests
with `429` and an empty body while the identical HTTP/2 request returns 200 — a
partial rollout, independent of account or IP. instaloader speaks HTTP/1.1 via
`requests`, so on an affected network *nothing* works and it looks exactly like
rate limiting. `_looks_like_the_http1_429` exists to tell the difference, because
"wait and retry" is the wrong advice for it.
"""

from __future__ import annotations

import asyncio
import urllib.request
from pathlib import Path

from instagram.media import Media, RateLimited, Unavailable
from instagram.reel import ReelRef

NAME = "instaloader"

# Instagram's CDN serves media to anyone, but rejects a default urllib agent.
_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0"

# The substrings instaloader/Instagram use for "you cannot have this". Matched on
# text because the library raises a small set of exception types for a much
# larger set of causes, and the cause is what the model needs to hear.
# "not available" with a space is the phrasing Instagram itself uses ("Requested
# content is not available, rate-limit reached or login required") and it does
# NOT contain the single word "unavailable" — a test caught the near-miss.
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
        # instaloader is synchronous and does blocking network I/O. Off the event
        # loop, or one fetch stalls every other reel in the same call — and the
        # call is already racing a 60s MCP deadline it cannot extend.
        return await asyncio.to_thread(self._fetch_blocking, ref, into)

    def _fetch_blocking(self, ref: ReelRef, into: Path) -> Media:
        import instaloader

        loader = instaloader.Instaloader(quiet=True, request_timeout=self._timeout)
        try:
            post = instaloader.Post.from_shortcode(loader.context, ref.shortcode)
        except Exception as err:  # noqa: BLE001 - the library raises many types for one meaning
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
            # `or ""` on caption only — the library returns None for a post with
            # no caption, which is different from a caption we failed to read.
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
    """The empty-bodied 429 that fires on the first request of a fresh session.

    Distinguished from a genuine throttle because the advice differs: a real
    limit clears by waiting, this one never does.
    """
    lowered = text.lower()
    return "429" in lowered and ("empty" in lowered or "json" in lowered or lowered.count(" ") < 6)


def _download(url: str, target: Path, timeout: float) -> Path:
    request = urllib.request.Request(url, headers={"User-Agent": _AGENT})
    # nosec: the URL comes from Instagram's own API response, not from a caller.
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        target.write_bytes(response.read())
    return target
