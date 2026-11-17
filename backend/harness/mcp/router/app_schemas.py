"""What an MCP app is sent, and what it asks: its HTML, the server list, a tool call."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AppResource(BaseModel):
    """An app's HTML and the policy to render it under."""

    model_config = ConfigDict(frozen=True)

    html: str
    csp: str


class ServerList(BaseModel):
    """The servers this harness is set up with, by namespace."""

    model_config = ConfigDict(frozen=True)

    servers: tuple[str, ...]


class AppToolCall(BaseModel):
    """What the app asks: a tool of its own server, and which app is asking."""

    model_config = ConfigDict(frozen=True)

    arguments: dict[str, object]
    resource_uri: str
