"""The blocks of `config.json`, one model each."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LLMSettings(BaseModel):
    """How every model is asked; which model a bot asks is its LLM credential."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    timeout_seconds: float = Field(default=600.0, gt=0)


class SessionSettings(BaseModel):
    """Where conversations are stored."""

    root: Path = Path.home() / ".harness" / "sessions"

    @field_validator("root")
    @classmethod
    def _expand(cls, value: Path) -> Path:
        return value.expanduser()


class ApprovalSettings(BaseModel):
    """Which tools ask the person before running, and where "always" is remembered."""

    tools: tuple[str, ...] = ()
    grants_path: Path = Path.home() / ".harness" / "approvals.json"

    @field_validator("grants_path")
    @classmethod
    def _expand(cls, value: Path) -> Path:
        return value.expanduser()


class BotSettings(BaseModel):
    """Where the bots and their instructions are kept."""

    path: Path = Path.home() / ".harness" / "bots.json"

    @field_validator("path")
    @classmethod
    def _expand(cls, value: Path) -> Path:
        return value.expanduser()


class SecretSettings(BaseModel):
    """Where the API keys bots ask for are kept, and the key that locks them."""

    path: Path = Path.home() / ".harness" / "secrets.json"
    encryption_key: str = ""

    @field_validator("path")
    @classmethod
    def _expand(cls, value: Path) -> Path:
        return value.expanduser()


class FileSettings(BaseModel):
    """Where each chat's files are kept, and the most one upload may be."""

    model_config = ConfigDict(frozen=True)

    root: Path = Path.home() / ".harness" / "files"
    max_bytes: int = Field(default=200 * 1024 * 1024, gt=0)

    @field_validator("root")
    @classmethod
    def _expand(cls, value: Path) -> Path:
        return value.expanduser()


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


class McpSettings(BaseModel):
    """Where the servers file is: every MCP server is added on the MCP servers screen."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path = Path.home() / ".harness" / "mcp.json"

    @field_validator("path")
    @classmethod
    def _expand(cls, value: Path) -> Path:
        return value.expanduser()
