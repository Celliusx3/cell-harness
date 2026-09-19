"""A `MediaSource` reading from local directories instead of Instagram."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from instagram.media import Media, RateLimited, Unavailable
from instagram.reel import ReelRef

NAME = "fixture"


class LocalFixtureSource:
    """Reads `Media` out of `root`, and can be told to fail on purpose."""

    def __init__(self, root: Path) -> None:
        self._root = root

    @property
    def name(self) -> str:
        return NAME

    async def fetch(self, ref: ReelRef, into: Path) -> Media:
        directory = self._root / ref.shortcode
        meta_path = directory / "meta.json"
        if not meta_path.is_file():
            raise Unavailable(f"no fixture for {ref.shortcode} under {self._root}")

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        outcome = meta.get("outcome", "ok")
        if outcome == "unavailable":
            raise Unavailable(meta.get("detail", f"{ref.shortcode} is unavailable"))
        if outcome == "rate_limited":
            raise RateLimited(
                meta.get("detail", "rate limited"),
                retry_after_seconds=meta.get("retry_after_seconds"),
            )
        if outcome != "ok":
            raise ValueError(f"fixture {ref.shortcode} has unknown outcome {outcome!r}")

        return Media(
            shortcode=ref.shortcode,
            video=_copy_if_present(directory / "video.mp4", into),
            thumbnail=_copy_if_present(directory / "thumbnail.jpg", into),
            caption=meta.get("caption", ""),
            author=meta.get("author", ""),
            hashtags=tuple(meta.get("hashtags", ())),
            mentions=tuple(meta.get("mentions", ())),
            tagged_users=tuple(meta.get("tagged_users", ())),
            posted_at=_parse_time(meta.get("posted_at")),
            duration_seconds=meta.get("duration_seconds"),
            source=NAME,
        )


def _copy_if_present(src: Path, into: Path) -> Path | None:
    if not src.is_file():
        return None
    into.mkdir(parents=True, exist_ok=True)
    target = into / src.name
    target.write_bytes(src.read_bytes())
    return target


def _parse_time(raw: str | None) -> datetime | None:
    if not raw:
        return None
    return datetime.fromisoformat(raw)
