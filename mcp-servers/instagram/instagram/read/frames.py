"""Sampling a video into a handful of frames, and its audio into a small upload."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from instagram.command import CommandRunner

FRAME_WIDTH = 512
FRAME_QUALITY = "6"


@dataclass(frozen=True)
class Sampled:
    paths: tuple[Path, ...]
    covered_seconds: float


class FfmpegFailed(RuntimeError):
    """ffmpeg exited non-zero. Carries its stderr, untruncated."""


async def sample_frames(
    video: Path,
    *,
    into: Path,
    max_frames: int,
    duration_seconds: float | None,
    ffmpeg: str,
    run: CommandRunner,
    timeout_seconds: float,
) -> Sampled:
    """Up to `max_frames` JPEGs spread evenly across the video."""
    into.mkdir(parents=True, exist_ok=True)
    for stale in into.glob("frame*.jpg"):
        stale.unlink()

    if duration_seconds and duration_seconds > 0:
        rate = f"{max_frames}/{duration_seconds}"
        covered = duration_seconds
    else:
        rate = "1/2"
        covered = 0.0

    argv = [
        ffmpeg,
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(video),
        "-vf",
        f"fps={rate},scale={FRAME_WIDTH}:-1",
        "-frames:v",
        str(max_frames),
        "-q:v",
        FRAME_QUALITY,
        str(into / "frame%02d.jpg"),
    ]
    result = await run(argv, timeout_seconds)
    if result.code != 0:
        raise FfmpegFailed(result.stderr or f"ffmpeg exited {result.code}")

    paths = tuple(sorted(into.glob("frame*.jpg")))
    return Sampled(paths=paths, covered_seconds=covered if paths else 0.0)


async def extract_audio(
    video: Path,
    *,
    into: Path,
    max_seconds: float,
    ffmpeg: str,
    run: CommandRunner,
    timeout_seconds: float,
) -> Path | None:
    """The first `max_seconds` of audio as 16 kHz mono mp3, or None if silent."""
    into.mkdir(parents=True, exist_ok=True)
    target = into / "audio.mp3"
    argv = [
        ffmpeg,
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(video),
        "-vn",
        "-t",
        f"{max_seconds:.0f}",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-b:a",
        "32k",
        str(target),
    ]
    result = await run(argv, timeout_seconds)
    if result.code != 0:
        # ffmpeg's two ways of saying "there was no audio to extract".
        no_audio_stderr = ("does not contain any stream", "Output file is empty")
        if any(marker in result.stderr for marker in no_audio_stderr):
            return None
        raise FfmpegFailed(result.stderr or f"ffmpeg exited {result.code}")
    if not target.is_file() or target.stat().st_size == 0:
        return None
    return target
