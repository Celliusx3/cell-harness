"""ffmpeg argv, which is the part that actually breaks — asserted without ffmpeg."""

from __future__ import annotations

from pathlib import Path

import pytest

from instagram.media import probe
from instagram.read import frames
from tests.conftest import recording_runner


def video(tmp_path: Path) -> Path:
    path = tmp_path / "video.mp4"
    path.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    return path


async def test_frames_are_spread_across_the_whole_video_not_taken_from_the_front(
    tmp_path: Path,
) -> None:
    """A 10-minute video sampled at a fixed interval returns twelve frames of its
    first 24 seconds while claiming to have covered the whole thing."""
    runner, calls = recording_runner(touch="frame")

    sampled = await frames.sample_frames(
        video(tmp_path),
        into=tmp_path / "out",
        max_frames=12,
        duration_seconds=600.0,
        ffmpeg="ffmpeg",
        run=runner,
        timeout_seconds=5,
    )

    argv = calls[0]
    assert "fps=12/600.0,scale=512:-1" in argv
    # The cap is enforced by ffmpeg too, not only by the rate.
    assert argv[argv.index("-frames:v") + 1] == "12"
    assert sampled.covered_seconds == 600.0


async def test_an_unknown_duration_falls_back_to_a_fixed_interval_and_claims_nothing(
    tmp_path: Path,
) -> None:
    """`covered_seconds: 0` is honest. Guessing a duration would make the
    `sampled_over_seconds` the model reads a lie."""
    runner, calls = recording_runner(touch="frame")

    sampled = await frames.sample_frames(
        video(tmp_path),
        into=tmp_path / "out",
        max_frames=8,
        duration_seconds=None,
        ffmpeg="ffmpeg",
        run=runner,
        timeout_seconds=5,
    )

    assert "fps=1/2,scale=512:-1" in calls[0]
    assert sampled.covered_seconds == 0.0


async def test_stale_frames_from_a_previous_read_are_not_counted_again(tmp_path: Path) -> None:
    """Globbed up alongside the new ones, they silently inflate `frames_read`."""
    out = tmp_path / "out"
    out.mkdir()
    for index in range(9):
        (out / f"frame9{index}.jpg").write_bytes(b"stale")
    runner, _ = recording_runner(touch="frame")

    sampled = await frames.sample_frames(
        video(tmp_path),
        into=out,
        max_frames=2,
        duration_seconds=4.0,
        ffmpeg="ffmpeg",
        run=runner,
        timeout_seconds=5,
    )

    assert len(sampled.paths) == 2


async def test_a_nonzero_ffmpeg_exit_carries_its_stderr_untruncated(tmp_path: Path) -> None:
    runner, _ = recording_runner(code=1, stderr="Invalid data found when processing input")

    with pytest.raises(frames.FfmpegFailed, match="Invalid data found"):
        await frames.sample_frames(
            video(tmp_path),
            into=tmp_path / "out",
            max_frames=2,
            duration_seconds=4.0,
            ffmpeg="ffmpeg",
            run=runner,
            timeout_seconds=5,
        )


async def test_audio_is_extracted_small_and_mono_rather_than_uploading_the_mp4(
    tmp_path: Path,
) -> None:
    """Measured: a 70s reel is 15MB as mp4 and 276KB as 16kHz mono mp3 — a 58x
    smaller upload for an identical transcript."""
    runner, calls = recording_runner(touch="audio")

    audio = await frames.extract_audio(
        video(tmp_path),
        into=tmp_path / "out",
        max_seconds=180,
        ffmpeg="ffmpeg",
        run=runner,
        timeout_seconds=5,
    )

    argv = calls[0]
    assert audio is not None and audio.name == "audio.mp3"
    assert "-vn" in argv
    assert argv[argv.index("-ar") + 1] == "16000"
    assert argv[argv.index("-ac") + 1] == "1"
    # The cap is what stops one long video eating the whole call budget.
    assert argv[argv.index("-t") + 1] == "180"


async def test_a_video_with_no_audio_stream_is_none_rather_than_a_failure(
    tmp_path: Path,
) -> None:
    """A reel with no audio track is ordinary; the caller reports it as unavailable."""
    runner, _ = recording_runner(code=1, stderr="Output file is empty, nothing was encoded")

    assert (
        await frames.extract_audio(
            video(tmp_path),
            into=tmp_path / "out",
            max_seconds=180,
            ffmpeg="ffmpeg",
            run=runner,
            timeout_seconds=5,
        )
        is None
    )


# --- the duration probe ---------------------------------------------------
#
# Added after a live run: instaloader returned `video_duration = None` for a real
# reel, so frames fell back to a fixed interval and the even-spreading guarantee
# became vacuous on exactly the long videos it exists for.


async def test_the_duration_is_probed_when_instaloader_does_not_report_one(
    tmp_path: Path,
) -> None:
    async def runner(argv, timeout: float):
        from instagram.command import Completed

        assert argv[0] == "ffprobe"
        assert "format=duration" in argv
        return Completed(code=0, stdout=b"69.958866\n", stderr="")

    seconds = await probe.probe_duration(
        video(tmp_path), ffprobe="ffprobe", run=runner, timeout_seconds=5
    )

    assert seconds == pytest.approx(69.958866)


@pytest.mark.parametrize(
    ("code", "stdout"),
    [
        (1, b""),  # ffprobe failed
        (0, b"N/A\n"),  # a container with no duration
        (0, b""),  # nothing at all
        (0, b"0\n"),  # zero is not a usable duration
    ],
)
async def test_an_unprobeable_duration_is_none_rather_than_a_guess(
    tmp_path: Path, code: int, stdout: bytes
) -> None:
    """Never raises: a missing or broken ffprobe is a degraded read, not a failed
    one, and None keeps the fixed-interval fallback intact."""

    async def runner(argv, timeout: float):
        from instagram.command import Completed

        return Completed(code=code, stdout=stdout, stderr="")

    assert (
        await probe.probe_duration(
            video(tmp_path), ffprobe="ffprobe", run=runner, timeout_seconds=5
        )
        is None
    )


async def test_a_missing_ffprobe_binary_does_not_fail_the_read(tmp_path: Path) -> None:
    async def runner(argv, timeout: float):
        raise OSError("No such file or directory: 'ffprobe'")

    assert (
        await probe.probe_duration(
            video(tmp_path), ffprobe="ffprobe", run=runner, timeout_seconds=5
        )
        is None
    )
