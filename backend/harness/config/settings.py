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
import shutil
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from harness.config.sections import (
    CodeModeSettings,
    CompactionSettings,
    DiscordSettings,
    LLMSettings,
    McpSettings,
    SessionSettings,
    TelegramSettings,
    WebSettings,
)

# backend/harness/config/settings.py → backend/
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_JSON = Path(os.getenv("HARNESS_CONFIG", _BACKEND_ROOT / "config.json"))
# Optional. A fresh clone has none, and every value it would hold has either a
# default or a loud error naming it.
_LOCAL_JSON = _CONFIG_JSON.with_name(_CONFIG_JSON.stem + ".local" + _CONFIG_JSON.suffix)


class SkillSettings(BaseModel):
    """Where skills are read from, in rank order, and where the editor writes.

    `.agents/skills` is the cross-client convention (agentskills.io): a skill
    installed by any other tool is visible here, and one saved from our settings
    page is visible to them. The project copy outranks the home copy, so a
    repository can pin its own version of a skill.

    Relative roots resolve against the project: the nearest `.git` ancestor of
    the config file, or the backend's parent when there is none.
    """

    model_config = ConfigDict(frozen=True)

    roots: tuple[Path, ...] = (Path(".agents/skills"), Path("~/.agents/skills"))
    editable: Path = Path("~/.agents/skills")

    @field_validator("roots", "editable")
    @classmethod
    def _resolve(cls, value: Path | tuple[Path, ...]) -> Path | tuple[Path, ...]:
        if isinstance(value, tuple):
            return tuple(_project_path(path) for path in value)
        return _project_path(value)

    @model_validator(mode="after")
    def _editable_is_read(self) -> SkillSettings:
        """A root nobody reads from is where 7.5's inert grant came from: the
        page would write a skill and the model would never see it."""
        if self.editable not in self.roots:
            raise ValueError(
                f"skills.editable {str(self.editable)!r} must be one of skills.roots, "
                "or what the editor saves is never read"
            )
        return self


def _project_path(path: Path) -> Path:
    expanded = path.expanduser()
    return expanded if expanded.is_absolute() else _project_root() / expanded


def _project_root() -> Path:
    for candidate in (_CONFIG_JSON.parent, *_CONFIG_JSON.parent.parents):
        if (candidate / ".git").exists():
            return candidate
    return _BACKEND_ROOT.parent


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
    discord: DiscordSettings = Field(default_factory=DiscordSettings)
    web: WebSettings = Field(default_factory=WebSettings)
    code: CodeModeSettings = Field(default_factory=CodeModeSettings)
    compaction: CompactionSettings = Field(default_factory=CompactionSettings)
    mcp: McpSettings = Field(default_factory=McpSettings)
    skills: SkillSettings = Field(default_factory=SkillSettings)

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
    if shutil.which(settings.code.deno_path) is None:
        raise MissingConfigError(
            f"{settings.code.deno_path!r} is not on PATH, and the harness runs "
            "every tool call through a Deno sandbox. Install Deno "
            f"(https://deno.com) or set code.deno_path in {_CONFIG_JSON}."
        )
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
