"""One settings object, from the environment, validated before the server binds."""

from __future__ import annotations

import os
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

BACKENDS = ("instaloader", "fixture")

DEFAULT_OCR_MODEL = "glm-5.3-flash"
DEFAULT_ASR_MODEL = "ilmu-asr-v4.2"


class ConfigError(RuntimeError):
    """Startup refused. The message names the variable to set."""


@dataclass(frozen=True)
class Config:
    provider_base_url: str
    provider_api_key: str
    vision_model: str
    asr_model: str
    media_backend: str
    work_dir: Path
    fixture_root: Path | None
    ffmpeg: str
    ffprobe: str
    max_frames: int
    max_speech_seconds: float
    fetch_concurrency: int
    read_concurrency: int
    call_budget_seconds: float
    request_timeout_seconds: float


def load(env: Mapping[str, str] | None = None) -> Config:
    """Build a `Config`, or raise `ConfigError`."""
    src = os.environ if env is None else env

    backend = src.get("INSTAGRAM_MEDIA_BACKEND", "instaloader").strip()
    if backend not in BACKENDS:
        raise ConfigError(
            f"INSTAGRAM_MEDIA_BACKEND={backend!r} is not one of {', '.join(BACKENDS)}"
        )

    fixture_root: Path | None = None
    if backend == "fixture":
        raw = src.get("INSTAGRAM_FIXTURE_ROOT", "").strip()
        if not raw:
            raise ConfigError("INSTAGRAM_MEDIA_BACKEND=fixture requires INSTAGRAM_FIXTURE_ROOT")
        fixture_root = Path(raw).expanduser()

    key = src.get("AI_PROVIDER_API_KEY", "").strip()
    if not key:
        raise ConfigError("AI_PROVIDER_API_KEY is not set")

    ffmpeg = src.get("INSTAGRAM_FFMPEG", "ffmpeg").strip()
    if shutil.which(ffmpeg) is None:
        raise ConfigError(f"{ffmpeg!r} is not on PATH; install ffmpeg or set INSTAGRAM_FFMPEG")

    base_url = src.get("AI_PROVIDER_BASE_URL", "").strip()
    if not base_url:
        raise ConfigError("AI_PROVIDER_BASE_URL is not set")

    ffprobe = src.get("INSTAGRAM_FFPROBE", "").strip()
    if not ffprobe:
        ffprobe = ffmpeg.replace("ffmpeg", "ffprobe")

    work_dir = Path(src.get("INSTAGRAM_WORK_DIR", "~/.harness/instagram")).expanduser()

    return Config(
        provider_base_url=base_url,
        provider_api_key=key,
        vision_model=src.get("AI_VISION_MODEL", DEFAULT_OCR_MODEL).strip(),
        asr_model=src.get("AI_ASR_MODEL", DEFAULT_ASR_MODEL).strip(),
        media_backend=backend,
        work_dir=work_dir,
        fixture_root=fixture_root,
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
        max_frames=_positive_int(src, "INSTAGRAM_MAX_FRAMES", 8),
        max_speech_seconds=_positive_float(src, "INSTAGRAM_MAX_SPEECH_SECONDS", 180.0),
        fetch_concurrency=_positive_int(src, "INSTAGRAM_FETCH_CONCURRENCY", 4),
        read_concurrency=_positive_int(src, "INSTAGRAM_READ_CONCURRENCY", 3),
        call_budget_seconds=_positive_float(src, "INSTAGRAM_CALL_BUDGET_SECONDS", 45.0),
        request_timeout_seconds=_positive_float(src, "INSTAGRAM_REQUEST_TIMEOUT_SECONDS", 120.0),
    )


def _positive_int(src: Mapping[str, str], name: str, default: int) -> int:
    raw = src.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as err:
        raise ConfigError(f"{name}={raw!r} is not an integer") from err
    if value <= 0:
        raise ConfigError(f"{name}={value} must be greater than zero")
    return value


def _positive_float(src: Mapping[str, str], name: str, default: float) -> float:
    raw = src.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as err:
        raise ConfigError(f"{name}={raw!r} is not a number") from err
    if value <= 0:
        raise ConfigError(f"{name}={value} must be greater than zero")
    return value
