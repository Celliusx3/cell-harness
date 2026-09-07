"""Audio to a transcript — and the guard that stops music becoming words.

**ASR on a music-only reel hallucinates instead of returning nothing.** Measured
on a real travel reel: sixteen seconds of background music transcribed as
`"bira bira bira bira"`. So an empty string is *not* the signal for "no speech",
and passing that text on would hand the model a transcript contradicting a
correct caption with no way to tell which to believe.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from instagram.read.http import ProviderHttp, strip_sentinels


@dataclass(frozen=True)
class Transcript:
    text: str
    language: str
    # False when the audio was speech-free and the model produced filler anyway.
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
    """Whether a transcript is ASR filler over music rather than speech.

    Measured shape: `"bira bira bira bira"` for sixteen seconds of a music-only
    reel. The signature is a short result made of very few distinct words, each
    repeated — which real speech of the same length never is.

    Deliberately conservative. A false positive discards a genuine short
    transcript, which loses supporting context; a false negative hands the model
    a confident fabrication it will reason from. The asymmetry favours discarding.
    """
    words = [w for w in re.split(r"\W+", text.lower()) if w]
    if not words:
        return True
    if len(words) > 12:
        return False
    return len(set(words)) <= max(1, len(words) // 3)
