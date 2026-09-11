"""Building the app the way the server does, for tests that drive HTTP.

Shared because there are three callers and the assembly is no longer one line:
the browser is a channel now, so an app needs a gateway, a chat repository and a
`WebChannel` registered into it. `build_channels` in `web/server.py` does the same
thing from `Settings` — which tests cannot use, because a bare `Settings()` reads
the developer's real `config.local.json` and would point the chat store at their
actual sessions directory.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from harness.channels.gateway import ChannelGateway
from harness.channels.repositories.jsonl import JsonlChatRepository
from harness.channels.web.channel import WebChannel
from harness.config.settings import McpServer
from harness.mcp.store import ClientFactory, McpServerStore, open_client
from harness.runs.store import RunStore
from harness.session.service import SessionService
from harness.skills import Catalog, SkillSnapshot
from harness.web.server import create_app


def web_gateway(
    tmp_path: Path, service: SessionService, runs: RunStore
) -> tuple[ChannelGateway, WebChannel]:
    """A gateway with only the browser registered."""
    gateway = ChannelGateway(JsonlChatRepository(tmp_path / "chats"), runs, service)
    web = WebChannel(service, runs, gateway)
    gateway.register(web)
    return gateway, web


def web_mcp(
    servers: dict[str, McpServer] | None = None,
    *,
    client_factory: ClientFactory = open_client,
) -> McpServerStore:
    """A store over whatever servers a test declares — none, by default.

    The factory is injectable so a test can connect to a fake in milliseconds
    instead of spawning a process.
    """
    return McpServerStore(servers or {}, client_factory=client_factory)


def web_app(
    tmp_path: Path,
    service: SessionService,
    runs: RunStore,
    *,
    mcp: McpServerStore | None = None,
    skills: Catalog = SkillSnapshot,
) -> FastAPI:
    """The application, wired as `create_web_app` wires it.

    `skills` defaults to an empty catalog — `SkillSnapshot()` with no arguments is one.
    """
    gateway, web = web_gateway(tmp_path, service, runs)
    return create_app(runs, gateway, web, mcp or web_mcp(), skills)
