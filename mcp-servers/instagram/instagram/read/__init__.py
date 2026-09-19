"""Turning fetched media into text observations, and nothing more."""

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


class Notes(list[str]):
    """What was noted while reading one reel, and whether a requested half failed."""

    failed: bool = False

    def fail(self, note: str) -> None:
        self.failed = True
        self.append(note)


@dataclass(frozen=True)
class Reader:
    """Everything reading needs, passed explicitly."""

    config: Config
    http: ProviderHttp
    run: CommandRunner


async def read_reel(shortcode: str, wanted: set[str], reader: Reader) -> ReadReel:
    """One reel's observations, degrading rather than failing."""
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
    notes = Notes()
    result = ReadReel(shortcode=shortcode, status="ok")

    if "visual" in wanted:
        result = await _add_visual(result, reader, directory, video, thumbnail, duration, notes)
    if "speech" in wanted:
        result = await _add_speech(result, reader, directory, video, duration, notes)

    return result.model_copy(
        update={"notes": list(notes), "status": "partial" if notes.failed else result.status}
    )


async def _add_visual(
    result: ReadReel,
    reader: Reader,
    directory: Path,
    video: Path | None,
    thumbnail: Path | None,
    duration: float | None,
    notes: Notes,
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
            paths, covered = (thumbnail,), 0.0
            notes.append("no video was available; only the poster image was read")
        else:
            notes.append("no image or video was available to read")
            return result

        description = await vision.describe(reader.http, paths, model=reader.config.vision_model)
    except Exception as err:
        logger.exception("visual read failed for %s", result.shortcode)
        notes.fail(f"visual failed: {type(err).__name__}: {err}")
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
    notes: Notes,
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
    except Exception as err:
        logger.exception("transcription failed for %s", result.shortcode)
        notes.fail(f"transcription failed: {type(err).__name__}: {err}")
        return result.model_copy(update={"speech": "failed"})

    transcribed = 0.0 if duration is None else min(capped, duration)
    if duration is not None and duration > capped:
        notes.append(f"transcribed the first {capped:.0f}s of {duration:.0f}s")
    if not transcript.is_speech:
        notes.append("the audio is music or ambience, not speech; no transcript was kept")
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
