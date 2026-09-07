"""Backend selection, and the error mapping that decides what the model hears."""

from __future__ import annotations

from pathlib import Path

import pytest

from instagram.media import RateLimited, Unavailable, source_for
from instagram.media.sources.fixture import LocalFixtureSource
from instagram.media.sources.instaloader import (
    InstaloaderSource,
    _translate,  # noqa: E402
)
from instagram.reel import ReelRef
from tests.conftest import make_config, write_fixture

REF = ReelRef(url="https://www.instagram.com/reel/C6NiA4lRux8/", shortcode="C6NiA4lRux8")


# --- selection ------------------------------------------------------------


def test_each_backend_name_builds_its_own_source(tmp_path: Path) -> None:
    instaloader = source_for(make_config(tmp_path, media_backend="instaloader"))
    fixture = source_for(make_config(tmp_path, media_backend="fixture"))

    assert isinstance(instaloader, InstaloaderSource)
    assert isinstance(fixture, LocalFixtureSource)
    # The name is reported back as `backend`, so a result says how it was obtained.
    assert (instaloader.name, fixture.name) == ("instaloader", "fixture")


def test_an_unknown_backend_raises_rather_than_defaulting(tmp_path: Path) -> None:
    """A silent default is how you end up debugging Instagram when the fixture
    backend was selected."""
    with pytest.raises(ValueError, match="no media backend named"):
        source_for(make_config(tmp_path, media_backend="hikerapi"))


def test_the_fixture_backend_without_a_root_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="INSTAGRAM_FIXTURE_ROOT"):
        source_for(make_config(tmp_path, media_backend="fixture", fixture_root=None))


# --- the error mapping ----------------------------------------------------


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
    """The library raises a small set of types for a much larger set of causes,
    and the cause is what the model needs to hear."""
    translated = _translate(Exception(message), REF)

    assert isinstance(translated, Unavailable)
    assert "private" in str(translated)


def test_a_genuine_throttle_becomes_rate_limited() -> None:
    translated = _translate(Exception("Please wait a few minutes before you try again"), REF)

    assert isinstance(translated, RateLimited)


def test_the_http1_429_is_distinguished_because_waiting_will_not_fix_it() -> None:
    """Instagram answers HTTP/1.1 web-API requests with an immediate empty 429
    while HTTP/2 returns 200. It presents as a rate limit and is not one, so the
    advice differs: a real limit clears by waiting, this one never does."""
    translated = _translate(Exception("429 empty response"), REF)

    assert isinstance(translated, RateLimited)
    message = str(translated)
    assert "HTTP/1.1" in message
    assert "waiting will not help" in message
    # No retry hint, because there is no delay that would help.
    assert translated.retry_after_seconds is None


def test_an_unrecognised_error_is_passed_through_rather_than_mislabelled() -> None:
    """Calling an unknown fault "unavailable" would tell the user their reel is
    private when the truth is a bug in us."""
    original = ValueError("something else entirely")

    assert _translate(original, REF) is original


# --- the fixture backend --------------------------------------------------


async def test_a_missing_fixture_raises_the_same_thing_a_missing_reel_does(
    tmp_path: Path,
) -> None:
    """Otherwise the failure-path tests exercise a code path the live backend never
    takes, and prove nothing."""
    source = LocalFixtureSource(tmp_path / "empty")

    with pytest.raises(Unavailable):
        await source.fetch(REF, tmp_path / "into")


async def test_media_is_copied_out_so_the_pipeline_never_writes_into_a_fixture(
    tmp_path: Path,
) -> None:
    """Frames are written beside the video and cleaned up afterwards; doing that
    in the checked-in fixture directory would mutate the repository."""
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
