"""`read_reels` through a real MCP client, in-process — and the regressions a
live run found that this suite had not.

Hermetic like `test_tools.py`: a fixture media backend and a mocked provider.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from instagram.command import Completed
from tests.conftest import (
    asr_reply,
    chat_reply,
    recording_runner,
    scripted,
    server_with,
    write_fixture,
)
from tests.unit.tools_helpers import VISION, call, server_for

# --- read -----------------------------------------------------------------


async def test_reading_before_fetching_says_so_and_says_what_to_do(work_dir: Path) -> None:
    result = await call(
        server_for(work_dir), "read_reels", {"shortcodes": ["OKvideo000"], "want": ["visual"]}
    )

    item = result.structured_content["items"][0]
    assert item["status"] == "not_fetched"
    assert "fetch_reels first" in item["detail"]


async def test_a_visual_read_returns_overlay_text_and_scene_separately(work_dir: Path) -> None:
    """One provider call yields both — measured, which is why `want` has no
    separate 'overlay_text' option."""
    server = server_for(work_dir)
    await call(server, "fetch_reels", {"urls": ["OKvideo000"]})

    result = await call(server, "read_reels", {"shortcodes": ["OKvideo000"], "want": ["visual"]})

    item = result.structured_content["items"][0]
    assert item["status"] == "ok"
    assert item["overlay_text"] == ["BEST NASI LEMAK", "@warung.mak.cik"]
    assert item["scene"] == "A roadside stall in Bangsar."
    assert item["frames_read"] > 0
    assert item["sampled_over_seconds"] == pytest.approx(2.0)


async def test_speech_is_not_transcribed_unless_asked_for(work_dir: Path) -> None:
    """It costs real time and tokens per reel and adds nothing to a silent one."""
    server = server_for(work_dir)
    await call(server, "fetch_reels", {"urls": ["OKvideo000"]})

    result = await call(server, "read_reels", {"shortcodes": ["OKvideo000"], "want": ["visual"]})

    item = result.structured_content["items"][0]
    assert item["speech"] == "skipped"
    assert item["transcript"] == ""


async def test_speech_is_returned_when_asked_for(work_dir: Path) -> None:
    server = server_for(work_dir)
    await call(server, "fetch_reels", {"urls": ["OKvideo000"]})

    result = await call(
        server, "read_reels", {"shortcodes": ["OKvideo000"], "want": ["visual", "speech"]}
    )

    item = result.structured_content["items"][0]
    assert item["speech"] == "present"
    assert "nasi lemak" in item["transcript"]


async def test_music_only_audio_is_none_and_its_hallucination_is_withheld(
    work_dir: Path,
) -> None:
    """Measured: a music-only reel transcribes as "bira bira bira bira". Passed
    through, the model gets a transcript contradicting a correct caption and no
    way to tell which to believe."""
    runner, _ = recording_runner(touch="x")
    handler = scripted(
        {"/chat/completions": VISION, "/audio/transcriptions": asr_reply("bira bira bira bira")}
    )
    server = server_with(work_dir, handler, runner)
    await call(server, "fetch_reels", {"urls": ["OKvideo000"]})

    result = await call(server, "read_reels", {"shortcodes": ["OKvideo000"], "want": ["speech"]})

    item = result.structured_content["items"][0]
    assert item["speech"] == "none"
    assert item["transcript"] == ""
    assert any("music or ambience" in note for note in item["notes"])
    # Still `ok`: a reel with only music is a complete answer, not a partial one.
    assert item["status"] == "ok"
    # And we say how much we listened to, which is a stronger claim than "none".
    assert item["speech_seconds"] == pytest.approx(2.0)


async def test_an_image_only_post_is_read_from_its_poster_and_says_so(work_dir: Path) -> None:
    """Degraded but real: a poster frame plus a caption is still evidence."""
    server = server_for(work_dir)
    await call(server, "fetch_reels", {"urls": ["OKimage000"]})

    result = await call(
        server, "read_reels", {"shortcodes": ["OKimage000"], "want": ["visual", "speech"]}
    )

    item = result.structured_content["items"][0]
    assert item["frames_read"] == 1
    assert any("poster image" in note for note in item["notes"])
    assert item["speech"] == "unavailable"


async def test_a_provider_failure_degrades_one_reel_to_partial_not_the_call(
    work_dir: Path,
) -> None:
    runner, _ = recording_runner(touch="x")
    handler = scripted({"/chat/completions": httpx.Response(503, text="upstream unavailable")})
    server = server_with(work_dir, handler, runner)
    await call(server, "fetch_reels", {"urls": ["OKvideo000"]})

    result = await call(server, "read_reels", {"shortcodes": ["OKvideo000"], "want": ["visual"]})

    item = result.structured_content["items"][0]
    assert item["status"] == "partial"
    assert any("visual failed" in note for note in item["notes"])
    assert any("503" in note for note in item["notes"])


async def test_no_legible_overlay_says_how_hard_it_looked(work_dir: Path) -> None:
    """ "We looked thoroughly and found nothing" is a different claim from "we did
    not look", and the model should be able to tell them apart."""
    runner, _ = recording_runner(touch="x")
    handler = scripted(
        {"/chat/completions": chat_reply("ON-SCREEN TEXT:\nNONE\n\nSCENE:\nA dark room.")}
    )
    server = server_with(work_dir, handler, runner)
    await call(server, "fetch_reels", {"urls": ["OKvideo000"]})

    result = await call(server, "read_reels", {"shortcodes": ["OKvideo000"], "want": ["visual"]})

    item = result.structured_content["items"][0]
    assert item["overlay_text"] == []
    assert any("no legible text overlay in" in note for note in item["notes"])


async def test_a_long_video_reports_the_transcription_bound_it_applied(
    work_dir: Path, tmp_path: Path
) -> None:
    """Bounded so one long video cannot eat the call budget — and *said*, so the
    model does not over-claim coverage."""
    root = tmp_path / "media"
    write_fixture(root, "LONG000000", {"outcome": "ok", "duration_seconds": 600.0}, video=True)
    runner, _ = recording_runner(touch="x")
    handler = scripted(
        {
            "/chat/completions": VISION,
            "/audio/transcriptions": asr_reply("A long narration about a fort."),
        }
    )
    server = server_with(work_dir, handler, runner, root=root, max_speech_seconds=180.0)
    await call(server, "fetch_reels", {"urls": ["LONG000000"]})

    result = await call(
        server, "read_reels", {"shortcodes": ["LONG000000"], "want": ["visual", "speech"]}
    )

    item = result.structured_content["items"][0]
    assert item["sampled_over_seconds"] == pytest.approx(600.0)
    assert item["speech_seconds"] == pytest.approx(180.0)
    assert any("first 180s of 600s" in note for note in item["notes"])


async def test_a_traversing_shortcode_is_one_bad_item_not_a_crash(work_dir: Path) -> None:
    result = await call(
        server_for(work_dir), "read_reels", {"shortcodes": ["../../etc/passwd"], "want": []}
    )

    item = result.structured_content["items"][0]
    assert item["status"] == "error"
    assert "not a usable shortcode" in item["detail"]


# --- regressions found by a live run, not by this suite -------------------


async def test_an_unknown_duration_is_probed_from_the_downloaded_video(
    work_dir: Path, tmp_path: Path
) -> None:
    """instaloader returned `duration_seconds: None` for a real reel."""
    root = tmp_path / "media"
    write_fixture(root, "NODUR00000", {"outcome": "ok", "caption": "x"}, video=True)

    async def runner(argv, timeout: float):
        if argv[0] == "ffprobe":
            return Completed(code=0, stdout=b"15.16\n", stderr="")
        return Completed(code=0, stdout=b"", stderr="")

    server = server_with(work_dir, scripted({"/chat/completions": VISION}), runner, root=root)

    result = await call(server, "fetch_reels", {"urls": ["NODUR00000"]})

    assert result.structured_content["items"][0]["duration_seconds"] == pytest.approx(15.16)


async def test_speech_seconds_is_never_the_cap_when_the_duration_is_unknown(
    work_dir: Path, tmp_path: Path
) -> None:
    """A live run reported `speech_seconds: 180.0` — the cap — for a 15-second
    video. That is a fabricated number the model would repeat to the user. 0.0
    means "we do not know", matching `sampled_over_seconds`."""
    root = tmp_path / "media"
    write_fixture(root, "NODUR00000", {"outcome": "ok"}, video=True)

    async def runner(argv, timeout: float):
        # No duration available from either instaloader or ffprobe.
        if argv[0] == "ffprobe":
            return Completed(code=1, stdout=b"", stderr="not probeable")
        target = Path(argv[-1])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"audiobytes")
        return Completed(code=0, stdout=b"", stderr="")

    server = server_with(
        work_dir,
        scripted({"/audio/transcriptions": asr_reply("A real spoken sentence here.")}),
        runner,
        root=root,
        max_speech_seconds=180.0,
    )
    await call(server, "fetch_reels", {"urls": ["NODUR00000"]})

    result = await call(server, "read_reels", {"shortcodes": ["NODUR00000"], "want": ["speech"]})

    item = result.structured_content["items"][0]
    assert item["speech"] == "present"
    assert item["speech_seconds"] == 0.0, "must not claim the cap as the amount transcribed"
    # And no bound is claimed, because none applied.
    assert not any("first 180s" in note for note in item["notes"])
