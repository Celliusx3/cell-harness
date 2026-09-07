"""Acquiring one reel, and turning the attempt into a result.

Lives beside the seam rather than in `tools/` because "what happened when we
tried to fetch this" is a fact about acquisition, not about MCP. `tools/` is left
holding only batching and the call budget.

Never raises for anything about *this* reel. The caller runs several of these
under one MCP call, and an exception would reach the model's script as a throw
that destroys every sibling result.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from instagram.command import CommandRunner
from instagram.config import Config
from instagram.media import Media, MediaSource, RateLimited, Unavailable, probe, store
from instagram.models import FetchedReel
from instagram.reel import ReelRef

logger = logging.getLogger("instagram.media")


@dataclass(frozen=True)
class Fetcher:
    """What acquiring needs. Deliberately no provider: fetching costs no tokens."""

    config: Config
    source: MediaSource
    run: CommandRunner


async def fetch_reel(ref: ReelRef, fetcher: Fetcher) -> FetchedReel:
    into = store.directory_for(fetcher.config.work_dir, ref.shortcode)
    try:
        media = await fetcher.source.fetch(ref, into)
    except Unavailable as err:
        return FetchedReel(
            url=ref.url, shortcode=ref.shortcode, status="unavailable", detail=str(err)
        )
    except RateLimited as err:
        return FetchedReel(
            url=ref.url,
            shortcode=ref.shortcode,
            status="rate_limited",
            detail=str(err),
            retry_after_seconds=err.retry_after_seconds,
        )
    except Exception as err:  # noqa: BLE001 - one item's bug must not reach the call
        logger.exception("fetch failed for %s", ref.shortcode)
        return FetchedReel(
            url=ref.url,
            shortcode=ref.shortcode,
            status="error",
            detail=f"{type(err).__name__}: {err}",
        )

    # instaloader does not always report a duration — observed live on a real
    # reel. Probed here rather than at read time because this is where the video
    # is already in hand, and because `read_reels` claiming a coverage it cannot
    # compute is the failure this prevents.
    duration = media.duration_seconds
    if duration is None and media.video is not None:
        duration = await probe.probe_duration(
            media.video,
            ffprobe=fetcher.config.ffprobe,
            run=fetcher.run,
            timeout_seconds=fetcher.config.request_timeout_seconds,
        )
    store.remember_duration(fetcher.config.work_dir, ref.shortcode, duration)

    return FetchedReel(
        url=ref.url,
        shortcode=media.shortcode,
        status="ok",
        media=_kind(media),
        duration_seconds=duration,
        author=media.author,
        caption=media.caption,
        hashtags=list(media.hashtags),
        mentions=list(media.mentions),
        tagged_users=list(media.tagged_users),
        posted_at=media.posted_at.isoformat() if media.posted_at else None,
        backend=media.source,
    )


def _kind(media: Media) -> str:
    if media.video is not None:
        return "video"
    if media.thumbnail is not None:
        return "image"
    return "none"
