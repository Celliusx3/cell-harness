"""Backend selection, and the error mapping that decides what the model hears."""

from __future__ import annotations

from pathlib import Path

import pytest

from instagram.media import RateLimited, Unavailable, source_for
from instagram.media.sources.fixture import LocalFixtureSource
from instagram.media.sources.instaloader import (
    InstaloaderSource,
    _translate,
)
from instagram.reel import ReelRef
from tests.conftest import make_config, write_fixture

REF = ReelRef(url="https://www.instagram.com/reel/C6NiA4lRux8/", shortcode="C6NiA4lRux8")


def test_each_backend_name_builds_its_own_source(tmp_path: Path) -> None:
    instaloader = source_for(make_config(tmp_path, media_backend="instaloader"))
    fixture = source_for(make_config(tmp_path, media_backend="fixture"))

    assert isinstance(instaloader, InstaloaderSource)
    assert isinstance(fixture, LocalFixtureSource)
    assert (instaloader.name, fixture.name) == ("instaloader", "fixture")


def test_an_unknown_backend_raises_rather_than_defaulting(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no media backend named"):
        source_for(make_config(tmp_path, media_backend="hikerapi"))


def test_the_fixture_backend_without_a_root_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="INSTAGRAM_FIXTURE_ROOT"):
        source_for(make_config(tmp_path, media_backend="fixture", fixture_root=None))


@pytest.mark.parametrize(
    "message",
    [
        "Post C6NiA4lRux8 does not exist",
        "Profile is private",
        "fetching Post metadata failed: login_required",
        "checkpoint_required",
        "HTTP error code 404",
        "Requested content is not available",
    ],
)
def test_every_way_instagram_says_no_becomes_unavailable(message: str) -> None:
    translated = _translate(Exception(message), REF)

    assert isinstance(translated, Unavailable)
    assert "private" in str(translated)


def test_a_genuine_throttle_becomes_rate_limited() -> None:
    translated = _translate(Exception("Please wait a few minutes before you try again"), REF)

    assert isinstance(translated, RateLimited)


def test_the_http1_429_is_distinguished_because_waiting_will_not_fix_it() -> None:
    translated = _translate(Exception("429 empty response"), REF)

    assert isinstance(translated, RateLimited)
    message = str(translated)
    assert "HTTP/1.1" in message
    assert "waiting will not help" in message
    assert translated.retry_after_seconds is None


def test_an_unrecognised_error_is_passed_through_rather_than_mislabelled() -> None:
    original = ValueError("something else entirely")

    assert _translate(original, REF) is original


async def test_a_missing_fixture_raises_the_same_thing_a_missing_reel_does(
    tmp_path: Path,
) -> None:
    source = LocalFixtureSource(tmp_path / "empty")

    with pytest.raises(Unavailable):
        await source.fetch(REF, tmp_path / "into")


async def test_media_is_copied_out_so_the_pipeline_never_writes_into_a_fixture(
    tmp_path: Path,
) -> None:
    root = tmp_path / "media"
    write_fixture(root, "AAAAAAAAAA", {"outcome": "ok", "caption": "hi"}, video=True)
    into = tmp_path / "work" / "AAAAAAAAAA"

    media = await LocalFixtureSource(root).fetch(
        ReelRef(url="AAAAAAAAAA", shortcode="AAAAAAAAAA"), into
    )

    assert media.video is not None
    assert media.video.parent == into
    assert (root / "AAAAAAAAAA" / "video.mp4").exists()


async def test_an_unknown_fixture_outcome_is_loud(tmp_path: Path) -> None:
    root = tmp_path / "media"
    write_fixture(root, "AAAAAAAAAA", {"outcome": "banana"})

    with pytest.raises(ValueError, match="unknown outcome"):
        await LocalFixtureSource(root).fetch(
            ReelRef(url="AAAAAAAAAA", shortcode="AAAAAAAAAA"), tmp_path / "into"
        )
