"""One settings object, from the environment, validated before the server binds.

**Fail closed, and refuse to start.** The harness mirrors this in
`config/settings.py:load()`: it will not boot with a blank model or key. The
payoff here is specific — a server that dies at startup is *absent from
`list_functions`*, so the model discovers it has no Instagram capability and says
so. A server that starts and then fails every call teaches the model to retry
a thing that cannot work.

No fallback chains. "One setting, one place to look" is a house rule, so there is
no `a or b`: each value has exactly one source, and an unusable one raises here
naming the variable to set.

**Two prefixes, because there are two kinds of setting.** `AI_*` configures the
model provider — its endpoint, its key, and which models to ask. `INSTAGRAM_*`
configures this server: where media lands, how many frames, how long a call may
take. The split is not cosmetic: the `AI_*` values are the ones another server
would need identically, and the `INSTAGRAM_*` ones are meaningless outside this
one. It also fixes a real confusion — `INSTAGRAM_PROVIDER_API_KEY` read as though
Instagram issued it, when Instagram needs no credential at all and the key is for
the model provider.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

# The backends `source_for` knows how to build. Listed here rather than inferred
# so an unknown name fails at startup with the valid set in the message, instead
# of at first call with a KeyError.
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
    """Build a `Config`, or raise `ConfigError`.

    `env` is injectable so tests can drive every refusal without touching the
    process environment — which would leak between tests and is the classic way
    a config test passes for the wrong reason.
    """
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
        # Required even for the fixture backend: reading a reel is a provider
        # call either way, and discovering the key is missing at the first
        # `read_reels` would present as a tool that half-works.
        raise ConfigError("AI_PROVIDER_API_KEY is not set")

    # `ffmpeg` cannot be a pip dependency, so unlike instaloader it is a PATH
    # requirement. Checked here so "no ffmpeg" is a refusal to start rather than
    # every read failing with a confusing OSError.
    ffmpeg = src.get("INSTAGRAM_FFMPEG", "ffmpeg").strip()
    if shutil.which(ffmpeg) is None:
        raise ConfigError(f"{ffmpeg!r} is not on PATH; install ffmpeg or set INSTAGRAM_FFMPEG")

    base_url = src.get("AI_PROVIDER_BASE_URL", "").strip()
    if not base_url:
        raise ConfigError("AI_PROVIDER_BASE_URL is not set")

    # Derived from ffmpeg rather than required: ffprobe ships in the same
    # package, and its absence only costs the duration probe — which already has
    # a fallback. Requiring it would refuse to start over a degraded read.
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
