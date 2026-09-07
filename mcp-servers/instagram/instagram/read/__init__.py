"""Turning fetched media into text observations, and nothing more.

This package reports what a reel shows and says. It never names a place, scores
a match, or looks anything up — that inference belongs to the harness model,
which sees the caption, the mentions, the on-screen text and the scene at once.
Keeping the refusal *here*, in the layer that has the pixels, is what makes the
boundary with the `places` server enforceable rather than aspirational.

Three modules, split from what was one 265-line `provider.py`, because they
changed for unrelated reasons: `http` is transport, `vision` is one question,
`speech` is another. `frames` is the ffmpeg work that feeds both.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from instagram.command import CommandRunner
from instagram.config import Config
from instagram.media import store
from instagram.models import ReadReel
from instagram.read import frames, speech, vision
from instagram.read.http import ProviderHttp, ProviderRateLimited

logger = logging.getLogger("instagram.read")

# A note that means "this half of what you asked for failed", as opposed to one
# that merely records a bound or an absence. `status` is decided from it, so the
# prefixes are load-bearing rather than cosmetic.
_FAILED_PREFIXES = ("visual failed", "transcription failed")


@dataclass(frozen=True)
class Reader:
    """Everything reading needs, passed explicitly.

    Separate from the fetch side's dependencies on purpose: reading needs a
    provider and ffmpeg and never touches Instagram, and a type that says so
    means a test can exercise the whole pipeline with no media backend at all.
    """

    config: Config
    http: ProviderHttp
    run: CommandRunner


async def read_reel(shortcode: str, wanted: set[str], reader: Reader) -> ReadReel:
    """One reel's observations, degrading rather than failing.

    Never raises for anything about *this* reel: the caller is running several of
    these under one call, and an exception here would reach the model's script as
    a throw that destroys every sibling result.
    """
    root = reader.config.work_dir
    try:
        if not store.has_media(root, shortcode):
            return ReadReel(
                shortcode=shortcode,
                status="not_fetched",
                detail=f"no media cached for {shortcode}; call fetch_reels first",
            )
    except ValueError as err:
        return ReadReel(shortcode=shortcode, status="error", detail=str(err))

    directory = store.directory_for(root, shortcode)
    video = store.video_in(root, shortcode)
    thumbnail = store.thumbnail_in(root, shortcode)
    duration = store.recall_duration(root, shortcode)
    notes: list[str] = []
    result = ReadReel(shortcode=shortcode, status="ok")

    if "visual" in wanted:
        result = await _add_visual(result, reader, directory, video, thumbnail, duration, notes)
    if "speech" in wanted:
        result = await _add_speech(result, reader, directory, video, duration, notes)

    # `partial` means "some of what you asked for is missing", so it is decided
    # by whether a requested half actually failed — not by `speech: unavailable`,
    # which is a complete answer about a reel that genuinely has no audio.
    failed = [note for note in notes if note.startswith(_FAILED_PREFIXES)]
    return result.model_copy(
        update={"notes": notes, "status": "partial" if failed else result.status}
    )


async def _add_visual(
    result: ReadReel,
    reader: Reader,
    directory: Path,
    video: Path | None,
    thumbnail: Path | None,
    duration: float | None,
    notes: list[str],
) -> ReadReel:
    try:
        if video is not None:
            sampled = await frames.sample_frames(
                video,
                into=directory,
                max_frames=reader.config.max_frames,
                duration_seconds=duration,
                ffmpeg=reader.config.ffmpeg,
                run=reader.run,
                timeout_seconds=reader.config.request_timeout_seconds,
            )
            paths, covered = sampled.paths, sampled.covered_seconds
        elif thumbnail is not None:
            # Degraded but real: a poster frame plus a caption is still evidence,
            # and saying so beats reporting the reel as unreadable.
            paths, covered = (thumbnail,), 0.0
            notes.append("no video was available; only the poster image was read")
        else:
            notes.append("no image or video was available to read")
            return result

        description = await vision.describe(reader.http, paths, model=reader.config.vision_model)
    except Exception as err:  # noqa: BLE001 - degrade this reel, never the call
        logger.exception("visual read failed for %s", result.shortcode)
        notes.append(f"visual failed: {type(err).__name__}: {err}")
        return result

    if not description.overlay_text:
        notes.append(
            f"no legible text overlay in {len(paths)} frame(s) sampled over {covered:.0f}s"
        )
    return result.model_copy(
        update={
            "overlay_text": list(description.overlay_text),
            "scene": description.scene,
            "frames_read": len(paths),
            "sampled_over_seconds": covered,
        }
    )


async def _add_speech(
    result: ReadReel,
    reader: Reader,
    directory: Path,
    video: Path | None,
    duration: float | None,
    notes: list[str],
) -> ReadReel:
    if video is None:
        return result.model_copy(update={"speech": "unavailable"})
    capped = reader.config.max_speech_seconds
    try:
        audio = await frames.extract_audio(
            video,
            into=directory,
            max_seconds=capped,
            ffmpeg=reader.config.ffmpeg,
            run=reader.run,
            timeout_seconds=reader.config.request_timeout_seconds,
        )
        if audio is None:
            return result.model_copy(update={"speech": "unavailable"})
        transcript = await speech.transcribe(reader.http, audio, model=reader.config.asr_model)
    except ProviderRateLimited as err:
        notes.append(f"transcription rate-limited: {err}")
        return result.model_copy(update={"speech": "failed"})
    except Exception as err:  # noqa: BLE001
        logger.exception("transcription failed for %s", result.shortcode)
        notes.append(f"transcription failed: {type(err).__name__}: {err}")
        return result.model_copy(update={"speech": "failed"})

    # Only claim a bound when one actually applied, and never claim the cap as
    # the amount transcribed: a live run reported `speech_seconds: 180.0` for a
    # 15-second video, which is a fabricated number the model would repeat to the
    # user. 0.0 means "we do not know", matching `sampled_over_seconds`.
    transcribed = 0.0 if duration is None else min(capped, duration)
    if duration is not None and duration > capped:
        notes.append(f"transcribed the first {capped:.0f}s of {duration:.0f}s")
    if not transcript.is_speech:
        notes.append("the audio is music or ambience, not speech; no transcript was kept")
        # `speech_seconds` is still reported: we listened to that much audio, and
        # "none over 15s" is a stronger claim than "none".
        return result.model_copy(
            update={"speech": "none", "transcript": "", "speech_seconds": transcribed}
        )

    return result.model_copy(
        update={
            "speech": "present",
            "transcript": transcript.text,
            "language": transcript.language,
            "speech_seconds": transcribed,
        }
    )
