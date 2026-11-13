"""The MCP servers screen's rows: each server, its keys, and its state."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from harness.mcp.domain.status import Status


class KeyState(BaseModel):
    """A key a server needs, by name, and whether its value is saved; never the value."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    is_set: bool


class ServerEntry(BaseModel):
    """One server as the screen lists it: how it runs, its keys, and its state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    command: str
    args: tuple[str, ...]
    env: dict[str, str]
    keys: tuple[KeyState, ...]
    status: Status
    error: str


class ServerEntries(BaseModel):
    """Every server, in the order each was added."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    servers: tuple[ServerEntry, ...]
