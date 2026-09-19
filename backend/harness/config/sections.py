"""The blocks of `config.json`, one model each."""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LLMSettings(BaseModel):
    """Which model answers, and how it is reached."""

    api_key: str = ""
    model: str = ""
    base_url: str = "https://api.openai.com/v1"
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    timeout_seconds: float = Field(default=600.0, gt=0)


class SessionSettings(BaseModel):
    """Where conversations are stored."""

    root: Path = Path.home() / ".harness" / "sessions"

    @field_validator("root")
    @classmethod
    def _expand(cls, value: Path) -> Path:
        return value.expanduser()


class TelegramSettings(BaseModel):
    """The bot to answer as, if any."""

    bot_token: str = ""


class DiscordSettings(BaseModel):
    """The Discord bot to answer as, if any. Off when empty, as Telegram's is."""

    bot_token: str = ""


class WebSettings(BaseModel):
    """Where the browser UI is reached from *outside* this machine."""

    public_url: str = ""

    @field_validator("public_url")
    @classmethod
    def _no_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")


class CodeModeSettings(BaseModel):
    """The sandbox the model's programs run in."""

    model_config = ConfigDict(frozen=True)

    deno_path: str = "deno"
    timeout_seconds: float = Field(default=60.0, gt=0)


class CompactionSettings(BaseModel):
    """When to shrink a conversation that has outgrown the model's window."""

    model_config = ConfigDict(frozen=True)

    context_tokens: int | None = Field(default=None, gt=0)


class McpServer(BaseModel):
    """One stdio MCP server, keyed in `McpSettings.servers` by its id."""

    model_config = ConfigDict(frozen=True)

    command: str
    args: tuple[str, ...] = ()
    env: dict[str, str] = Field(default_factory=dict)

    @field_validator("command")
    @classmethod
    def _spawnable(cls, value: str) -> str:
        """A config that cannot work is a startup failure, not a silent no-op."""
        if not value.strip():
            raise ValueError("command must not be blank")
        return value


class McpSettings(BaseModel):
    """Which MCP servers to connect at startup."""

    servers: dict[str, McpServer] = Field(default_factory=dict)

    @field_validator("servers")
    @classmethod
    def _usable_ids(cls, value: dict[str, McpServer]) -> dict[str, McpServer]:
        """Ids must survive being half of a tool name, and half of an identifier."""
        for name in value:
            if not _SERVER_ID.match(name):
                raise ValueError(
                    f"{name!r} is not a usable MCP server id: a lowercase letter followed "
                    "by lowercase letters or digits, at most 32. No underscore, because it "
                    "would make the {server}__{tool} split ambiguous; no hyphen and no "
                    "leading digit, because {server}__{tool} becomes a TypeScript identifier "
                    "in code mode"
                )
        return value


_SERVER_ID = re.compile(r"^[a-z][a-z0-9]{0,31}$")
