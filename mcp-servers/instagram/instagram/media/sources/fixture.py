"""A `MediaSource` reading from local directories instead of Instagram.

Two jobs, and the second is why it ships rather than living in `tests/`:

1. It is the seam every hermetic test drives. Instagram cannot be in CI, so the
   only honest way to test "we handle every shape a backend can hand us" is a
   backend we control.
2. It is a **real path**. Someone hands you an mp4, or you want to re-run the
   pipeline over media you already have, and `INSTAGRAM_MEDIA_BACKEND=fixture`
   without touching Instagram at all.

That second job is what keeps it out of `tests/`: the house rule is that a
definition whose only callers are tests belongs in tests. This one is reachable
by configuration, which is the point.

Layout, one directory per shortcode:

    <root>/<shortcode>/video.mp4        optional
    <root>/<shortcode>/thumbnail.jpg    optional
    <root>/<shortcode>/meta.json        required
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from instagram.media import Media, RateLimited, Unavailable
from instagram.reel import ReelRef

NAME = "fixture"


class LocalFixtureSource:
    """Reads `Media` out of `root`, and can be told to fail on purpose.

    `meta.json` may carry an `outcome` of `unavailable` or `rate_limited`, which
    raises rather than returns. Without it there would be no way to exercise the
    failure statuses at all, and those are exactly the paths that go untested and
    then misbehave in front of a user.
    """

    def __init__(self, root: Path) -> None:
        self._root = root

    @property
    def name(self) -> str:
        return NAME

    async def fetch(self, ref: ReelRef, into: Path) -> Media:
        directory = self._root / ref.shortcode
        meta_path = directory / "meta.json"
        if not meta_path.is_file():
            # Deliberately the same exception a real backend raises for a post it
            # cannot serve: a fixture that is missing and a reel that is gone
            # should exercise the same code path, or the test proves nothing.
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
            # Copied into `into` rather than referenced in place, so the rest of
            # the pipeline treats fixture and live media identically — including
            # writing frames beside the video and cleaning up afterwards, which
            # must never touch a checked-in fixture.
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
