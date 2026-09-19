"""Building the app the way the server does, for tests that drive HTTP."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from harness.channels.gateway import ChannelGateway
from harness.channels.repositories.jsonl import JsonlChatRepository
from harness.channels.web.channel import WebChannel
from harness.config.sections import McpServer
from harness.mcp.client import ClientFactory, open_client
from harness.mcp.store import McpServerStore
from harness.runs.store import RunStore
from harness.session.service import SessionService
from harness.skills import SkillService
from harness.tools.client import ClientToolService
from harness.web.server import create_app
from tests.unit.helpers import client_tools as default_client_tools


def web_gateway(
    tmp_path: Path,
    service: SessionService,
    runs: RunStore,
    *,
    skills: SkillService,
    client_tools: ClientToolService,
) -> tuple[ChannelGateway, WebChannel]:
    """A gateway with only the browser registered."""
    gateway = ChannelGateway(
        JsonlChatRepository(tmp_path / "chats"),
        runs,
        service,
        skills,
        public_url="http://t",
        client_tools=client_tools.names,
    )
    web = WebChannel(service, runs, gateway)
    gateway.register(web)
    return gateway, web


def web_mcp(
    servers: dict[str, McpServer] | None = None,
    *,
    client_factory: ClientFactory = open_client,
) -> McpServerStore:
    """A store over whatever servers a test declares — none, by default."""
    return McpServerStore(servers or {}, client_factory=client_factory)


def web_app(
    tmp_path: Path,
    service: SessionService,
    runs: RunStore,
    *,
    mcp: McpServerStore | None = None,
    skills: SkillService,
    client_tools: ClientToolService | None = None,
) -> FastAPI:
    """The application, wired as `create_web_app` wires it."""
    client_tools = client_tools or default_client_tools()
    gateway, web = web_gateway(tmp_path, service, runs, skills=skills, client_tools=client_tools)
    return create_app(runs, gateway, web, mcp or web_mcp(), skills, client_tools)
