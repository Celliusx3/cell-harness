"""Acquiring one reel, and turning the attempt into a result."""

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
    """What acquiring needs."""

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
    except Exception as err:
        logger.exception("fetch failed for %s", ref.shortcode)
        return FetchedReel(
            url=ref.url,
            shortcode=ref.shortcode,
            status="error",
            detail=f"{type(err).__name__}: {err}",
        )

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
