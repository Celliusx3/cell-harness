"""The blocks of `config.json`, one model each."""

from __future__ import annotations

import re
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


class McpServer(BaseModel):
    """One stdio MCP server as it is run, keyed by its id in the servers file."""

    model_config = ConfigDict(frozen=True)

    command: str
    args: tuple[str, ...] = ()
    env: dict[str, str] = Field(default_factory=dict)
    needs: tuple[str, ...] = ()

    @field_validator("command")
    @classmethod
    def _spawnable(cls, value: str) -> str:
        """A config that cannot work is a startup failure, not a silent no-op."""
        return spawnable_command(value)

    @field_validator("env")
    @classmethod
    def _home_expanded(cls, value: dict[str, str]) -> dict[str, str]:
        """A setting that starts with `~/` names a path in the home folder of whoever runs it."""
        return {
            name: str(Path(setting).expanduser()) if setting.startswith("~/") else setting
            for name, setting in value.items()
        }

    @field_validator("needs")
    @classmethod
    def _named(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Each key the server waits for is named by the env variable it is passed in."""
        return named_keys(value)


class McpSettings(BaseModel):
    """Where the servers file is: every MCP server is added on the MCP servers screen."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path = Path.home() / ".harness" / "mcp.json"

    @field_validator("path")
    @classmethod
    def _expand(cls, value: Path) -> Path:
        return value.expanduser()


_SERVER_ID = re.compile(r"^[a-z][a-z0-9]{0,31}$")


def usable_server_id(name: str) -> str:
    """`name`, if it can be half of a tool name and half of an identifier; `ValueError` if not."""
    if not _SERVER_ID.match(name):
        raise ValueError(
            f"{name!r} is not a usable MCP server id: a lowercase letter followed "
            "by lowercase letters or digits, at most 32. No underscore, because it "
            "would make the {server}__{tool} split ambiguous; no hyphen and no "
            "leading digit, because {server}__{tool} becomes a TypeScript identifier "
            "in code mode"
        )
    return name


def spawnable_command(value: str) -> str:
    """`value`, if it names something to run; `ValueError` for a blank one."""
    if not value.strip():
        raise ValueError("command must not be blank")
    return value


def named_keys(value: tuple[str, ...]) -> tuple[str, ...]:
    """`value`, if each key is named by an env variable; `ValueError` for a blank name."""
    if any(not name.strip() for name in value):
        raise ValueError("needs must name env variables, none blank")
    return value
