"""Transcription, and the guard that stops music becoming words."""

from __future__ import annotations

from pathlib import Path

import pytest

from instagram.read import speech
from tests.conftest import asr_reply, http_with, scripted


def frame(tmp_path: Path) -> Path:
    path = tmp_path / "frame01.jpg"
    path.write_bytes(b"jpegbytes")
    return path


@pytest.mark.parametrize(
    "text",
    [
        "bira bira bira bira",
        "la la la la la la",
        "",
        "   ",
        "Music Music Music",
    ],
)
def test_music_filler_is_recognised_as_not_speech(text: str) -> None:
    assert speech.is_music_not_speech(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "It is called Natalina Italian Kitchen located in Avenue K.",
        "This is where you can find one of the best Italian food in KL.",
        "Best nasi lemak in Bangsar, open seven to eleven.",
    ],
)
def test_real_speech_is_not_discarded_as_music(text: str) -> None:
    assert speech.is_music_not_speech(text) is False


async def test_a_music_only_transcript_is_reported_as_not_speech(tmp_path: Path) -> None:
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"audiobytes")
    http = http_with(scripted({"/audio/transcriptions": asr_reply("bira bira bira bira")}))

    transcript = await speech.transcribe(http, audio, model="m")

    assert transcript.is_speech is False
    assert transcript.text == "bira bira bira bira"
