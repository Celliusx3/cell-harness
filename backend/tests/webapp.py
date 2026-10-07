"""Building the app the way the server does, for tests that drive HTTP."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI

from harness.bots import ASSISTANT_INSTRUCTIONS, BotStore
from harness.channels.gateway import ChannelGateway
from harness.channels.repositories.jsonl import JsonlChatRepository
from harness.channels.web.channel import WebChannel
from harness.config.sections import McpServer
from harness.mcp.client import ClientFactory, open_client
from harness.mcp.store import McpServerStore
from harness.runs.store import RunStore
from harness.session.service import SessionService
from harness.skills import SkillService
from harness.tools.approval import ApprovalGate
from harness.tools.client import ClientToolService
from harness.web.server import create_app
from tests.unit.helpers import client_tools as default_client_tools
from tests.unit.helpers import no_bots, no_gate
from tests.unit.telegram_fakes import FakeBot, telegram_channel


def bots_in(tmp_path: Path, service: SessionService) -> BotStore:
    """Assistant and any bot a test makes, kept in a bots file under `tmp_path`."""
    return BotStore(tmp_path / "bots.json", service, assistant_instructions=ASSISTANT_INSTRUCTIONS)


def web_gateway(
    tmp_path: Path,
    service: SessionService,
    runs: RunStore,
    *,
    skills: SkillService,
    bots: BotStore | None = None,
) -> tuple[ChannelGateway, WebChannel]:
    """A gateway with only the browser registered."""
    gateway = ChannelGateway(
        JsonlChatRepository(tmp_path / "chats"),
        runs,
        service,
        skills,
        public_url="http://t",
    )
    web = WebChannel(service, runs, gateway, bots or bots_in(tmp_path, service))
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
    gate: ApprovalGate | None = None,
    bots: BotStore | None = None,
) -> FastAPI:
    """The application, wired as `create_web_app` wires it."""
    client_tools = client_tools or default_client_tools()
    bots = bots or bots_in(tmp_path, service)
    gateway, web = web_gateway(tmp_path, service, runs, skills=skills, bots=bots)
    return create_app(
        runs, gateway, web, mcp or web_mcp(), skills, client_tools, gate or no_gate(), bots
    )


def web_app_with_telegram(
    tmp_path: Path,
    service: SessionService,
    runs: RunStore,
    *,
    skills: SkillService,
    client_tools: ClientToolService | None = None,
    gate: ApprovalGate | None = None,
) -> tuple[FastAPI, ChannelGateway, FakeBot]:
    """`web_app` with a fake Telegram on the same gateway: the app, the gateway, and the bot."""
    bots = no_bots(service)
    gateway, web = web_gateway(tmp_path, service, runs, skills=skills, bots=bots)
    channel, bot = telegram_channel(gateway)
    gateway.register(channel)
    app = create_app(
        runs,
        gateway,
        web,
        web_mcp(),
        skills,
        client_tools or default_client_tools(),
        gate or no_gate(),
        bots,
    )
    return app, gateway, bot


async def idle(runs: RunStore, gateway: ChannelGateway) -> None:
    """Wait for every turn and every chat's delivery to finish."""
    for _ in range(300):
        if not gateway._tasks.running() and not runs._runs:
            return
        await asyncio.sleep(0.01)
    raise AssertionError("the gateway never went idle")
