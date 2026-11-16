"""Settings read from two JSON files, one committed and one not, and the environment."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from harness.config.domain.sections import (
    ApprovalSettings,
    AskSettings,
    BotSettings,
    CodeModeSettings,
    CompactionSettings,
    FileSettings,
    GroupSettings,
    LLMSettings,
    McpSettings,
    ScheduleSettings,
    SecretSettings,
    SessionSettings,
    TicketSettings,
    WebSettings,
)

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
CONFIG_JSON = Path(os.getenv("HARNESS_CONFIG", _BACKEND_ROOT / "config.json"))
LOCAL_JSON = Path(
    os.getenv(
        "HARNESS_CONFIG_LOCAL",
        CONFIG_JSON.with_name(CONFIG_JSON.stem + ".local" + CONFIG_JSON.suffix),
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
    def _require_editable_in_roots(self) -> SkillSettings:
        """Raise unless the editable root is also one the model reads from."""
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
    for candidate in (CONFIG_JSON.parent, *CONFIG_JSON.parent.parents):
        if (candidate / ".git").exists():
            return candidate
    return _BACKEND_ROOT.parent


class Settings(BaseSettings):
    """Everything the harness is configured with, loaded once."""

    model_config = SettingsConfigDict(
        env_prefix="HARNESS_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="forbid",
        hide_input_in_errors=True,
    )

    llm: LLMSettings = Field(default_factory=LLMSettings)
    sessions: SessionSettings = Field(default_factory=SessionSettings)
    web: WebSettings = Field(default_factory=WebSettings)
    code: CodeModeSettings = Field(default_factory=CodeModeSettings)
    compaction: CompactionSettings = Field(default_factory=CompactionSettings)
    mcp: McpSettings = Field(default_factory=McpSettings)
    skills: SkillSettings = Field(default_factory=SkillSettings)
    approval: ApprovalSettings = Field(default_factory=ApprovalSettings)
    bots: BotSettings = Field(default_factory=BotSettings)
    groups: GroupSettings = Field(default_factory=GroupSettings)
    schedules: ScheduleSettings = Field(default_factory=ScheduleSettings)
    tickets: TicketSettings = Field(default_factory=TicketSettings)
    secrets: SecretSettings = Field(default_factory=SecretSettings)
    files: FileSettings = Field(default_factory=FileSettings)
    ask: AskSettings = Field(default_factory=AskSettings)

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
        local = JsonConfigSettingsSource(settings_cls, json_file=LOCAL_JSON)
        committed = JsonConfigSettingsSource(settings_cls, json_file=CONFIG_JSON)
        return (init_settings, env_settings, local, committed)


class SettingsRepository:
    """The settings in the two JSON files and the environment, read whole."""

    @property
    def committed_path(self) -> Path:
        """The committed `config.json`."""
        return CONFIG_JSON

    @property
    def local_path(self) -> Path:
        """The gitignored `config.local.json`, which wins over the committed file."""
        return LOCAL_JSON

    def read(self) -> Settings:
        """Every setting, the environment first, then the local file, then the committed one."""
        return Settings()
