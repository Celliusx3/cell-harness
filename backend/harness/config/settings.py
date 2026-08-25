"""Settings: two JSON files, one committed and one not.

Loading priority, highest wins — syndesis's layering, with its `.env` folded into
a second JSON file so there is only one format to know:

    1. constructor kwargs          (tests, explicit composition)
    2. environment variables       HARNESS_LLM__MODEL=…
    3. `config.local.json`         gitignored: secrets and local overrides
    4. `config.json`               committed: how the harness runs by default

The two JSON files have the **same shape**, so overriding something is copying
its block and changing the value — no translation between a nested document and
flat `SCREAMING__SNAKE` names. That translation is the only reason a `.env` would
still be here; without it, `.env` is a second format for the same job.

Environment variables remain, because that is how CI and containers inject
configuration — nothing reads a file there. They nest with `__`
(`HARNESS_LLM__API_KEY`), and the `HARNESS_` prefix is deliberate: a harness that
picked up a bare `LLM__API_KEY` from someone's shell would be a surprising thing
to debug.

**One `Settings`, not one class per concern.** Nested groups mean `settings.llm`
and `settings.sessions` come from one object loaded once. Two independent
`BaseSettings` would each parse the files separately and give "where does this
value come from?" two answers — the failure mode the house rules name.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

# backend/harness/config/settings.py → backend/
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_JSON = Path(os.getenv("HARNESS_CONFIG", _BACKEND_ROOT / "config.json"))
# Optional. A fresh clone has none, and every value it would hold has either a
# default or a loud error naming it.
_LOCAL_JSON = _CONFIG_JSON.with_name(_CONFIG_JSON.stem + ".local" + _CONFIG_JSON.suffix)


class LLMSettings(BaseModel):
    """Which model answers, and how it is reached."""

    # No default: a default API key cannot exist, and a default *model* is a
    # behavioral choice — it decides what answers cost and how good they are, so
    # inheriting one silently is the "where did this come from?" bug the house
    # rules forbid. Both come from config.json or the environment.
    api_key: str = ""
    model: str = ""
    # Any OpenAI-compatible /chat/completions endpoint: OpenAI, DeepSeek,
    # Together, vLLM, Ollama.
    base_url: str = "https://api.openai.com/v1"
    # Pinned rather than omitted: leaving it unset means inheriting whatever the
    # provider currently defaults to, which can change without our code moving.
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    # Whole-request budget. Generous: it bounds a streaming call that may
    # legitimately think for a while, and exists so a hung connection surfaces as
    # a failed turn rather than a process that never returns.
    timeout_seconds: float = Field(default=600.0, gt=0)


class SessionSettings(BaseModel):
    """Where conversations are stored."""

    # A fixed home-relative default, never a cwd-relative one — dsh's objection
    # is that `process.cwd()` scatters logs as the working directory moves
    # (a bash call, a subprocess). `~` is expanded below so config.json can hold
    # the readable form.
    root: Path = Path.home() / ".harness" / "sessions"

    @field_validator("root")
    @classmethod
    def _expand(cls, value: Path) -> Path:
        return value.expanduser()


class TelegramSettings(BaseModel):
    """The bot to answer as, if any."""

    # Empty means the channel is off, which is the only sensible default: a token
    # cannot be guessed, and a harness that refused to start without one would be
    # unusable for everyone running it in a browser.
    bot_token: str = ""


class Settings(BaseSettings):
    """Everything the harness is configured with, loaded once."""

    model_config = SettingsConfigDict(
        env_prefix="HARNESS_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    llm: LLMSettings = Field(default_factory=LLMSettings)
    sessions: SessionSettings = Field(default_factory=SessionSettings)
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Highest priority first. `config.json` is last, so it is the floor
        every other source overrides rather than a thing that overrides them.

        A missing file contributes nothing rather than failing, which is what
        lets `config.local.json` be optional and `config.json` be absent in a
        deployment configured entirely through the environment.
        """
        return (
            init_settings,
            env_settings,
            JsonConfigSettingsSource(settings_cls, json_file=_LOCAL_JSON),
            JsonConfigSettingsSource(settings_cls, json_file=_CONFIG_JSON),
        )


class MissingConfigError(RuntimeError):
    """A value with no possible default was not supplied anywhere."""


def load() -> Settings:
    """Settings for a real run, with the two unguessable values checked.

    Validated here rather than as required fields, because a required field
    would make `Settings()` unusable in the many tests that do not care about a
    model — and because the error a caller wants names the file to edit, not a
    pydantic field path.
    """
    settings = Settings()
    missing = [
        name
        for name, value in (("model", settings.llm.model), ("api_key", settings.llm.api_key))
        if not value.strip()
    ]
    if missing:
        names = " and ".join(f"llm.{name}" for name in missing)
        verb = "is" if len(missing) == 1 else "are"
        raise MissingConfigError(
            f"{names} {verb} not set. Non-secret values belong in {_CONFIG_JSON}; "
            f"the API key belongs in {_LOCAL_JSON} (gitignored) as "
            f'{{"llm": {{"api_key": "…"}}}}, or in HARNESS_LLM__API_KEY.'
        )
    return settings
