"""One MCP server as it is run, and the rules its id, command and key names follow."""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


_SERVER_ID_PATTERN = re.compile(r"^[a-z][a-z0-9]{0,31}$")


def usable_server_id(name: str) -> str:
    """`name`, if it can be half of a tool name and half of an identifier; `ValueError` if not."""
    if not _SERVER_ID_PATTERN.match(name):
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
