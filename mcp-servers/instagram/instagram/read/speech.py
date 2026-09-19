"""Audio to a transcript — and the guard that stops music becoming words."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from instagram.read.http import ProviderHttp, strip_sentinels


@dataclass(frozen=True)
class Transcript:
    text: str
    language: str
    is_speech: bool


async def transcribe(http: ProviderHttp, audio: Path, *, model: str) -> Transcript:
    """Whisper-compatible multipart. Music is reported as not-speech."""
    body = await http.post_file("/audio/transcriptions", audio, {"model": model})
    text = strip_sentinels(str(body.get("text", "")))
    return Transcript(
        text=text,
        language=str(body.get("language", "")),
        is_speech=not is_music_not_speech(text),
    )


def is_music_not_speech(text: str) -> bool:
    """Whether a transcript is ASR filler over music rather than speech."""
    words = [w for w in re.split(r"\W+", text.lower()) if w]
    if not words:
        return True
    if len(words) > 12:
        return False
    return len(set(words)) <= max(1, len(words) // 3)
