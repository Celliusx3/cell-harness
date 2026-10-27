"""Settings: two JSON files, one committed and one not."""

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
    ApprovalSettings,
    BotSettings,
    CodeModeSettings,
    CompactionSettings,
    FileSettings,
    LLMSettings,
    McpSettings,
    SecretSettings,
    SessionSettings,
    WebSettings,
)

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_JSON = Path(os.getenv("HARNESS_CONFIG", _BACKEND_ROOT / "config.json"))
_LOCAL_JSON = Path(
    os.getenv(
        "HARNESS_CONFIG_LOCAL",
        _CONFIG_JSON.with_name(_CONFIG_JSON.stem + ".local" + _CONFIG_JSON.suffix),
    )
)


class SkillSettings(BaseModel):
    """Where skills are read from, in rank order, and where the editor writes."""

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
        """Whether the editable root is also one the model reads from."""
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

    local_settings_path: Path = Field(exclude=True)
    llm: LLMSettings
    sessions: SessionSettings = Field(default_factory=SessionSettings)
    web: WebSettings = Field(default_factory=WebSettings)
    code: CodeModeSettings = Field(default_factory=CodeModeSettings)
    compaction: CompactionSettings = Field(default_factory=CompactionSettings)
    mcp: McpSettings = Field(default_factory=McpSettings)
    skills: SkillSettings = Field(default_factory=SkillSettings)
    approval: ApprovalSettings = Field(default_factory=ApprovalSettings)
    bots: BotSettings = Field(default_factory=BotSettings)
    secrets: SecretSettings = Field(default_factory=SecretSettings)
    files: FileSettings = Field(default_factory=FileSettings)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Highest priority first."""
        return (
            init_settings,
            env_settings,
            JsonConfigSettingsSource(settings_cls, json_file=_LOCAL_JSON),
            JsonConfigSettingsSource(settings_cls, json_file=_CONFIG_JSON),
        )


class MissingConfigError(RuntimeError):
    """A value with no possible default was not supplied anywhere."""


def load() -> Settings:
    """Settings for a real run, with the two unguessable values checked."""
    settings = Settings(local_settings_path=_LOCAL_JSON)
    if shutil.which(settings.code.deno_path) is None:
        raise MissingConfigError(
            f"{settings.code.deno_path!r} is not on PATH, and the harness runs "
            "every tool call through a Deno sandbox. Install Deno "
            f"(https://deno.com) or set code.deno_path in {_CONFIG_JSON}."
        )
    if not settings.llm.model.strip():
        raise MissingConfigError(f"llm.model is not set. It belongs in {_CONFIG_JSON}.")
    if not settings.secrets.encryption_key.strip():
        raise MissingConfigError(
            f"secrets.encryption_key is not set. It belongs in {_LOCAL_JSON} (gitignored) as "
            f'{{"secrets": {{"encryption_key": "…"}}}}, or in HARNESS_SECRETS__ENCRYPTION_KEY. '
            "Make one with `openssl rand -hex 32`. Changing it makes every saved key unreadable."
        )
    return settings
