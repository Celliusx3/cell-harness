"""The composition root, and the ASGI application."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from harness.channels.client import ChatAnswers
from harness.channels.discord.channel import DiscordChannel
from harness.channels.gateway import ChannelGateway
from harness.channels.repositories.jsonl import JsonlChatRepository
from harness.channels.telegram.channel import TelegramChannel
from harness.channels.web.channel import WebChannel
from harness.config.settings import Settings, load
from harness.llm.adapters.models import context_length
from harness.mcp.store import McpServerStore
from harness.runs.store import RunStore
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.skills import SkillService
from harness.tools.approval import ApprovalGate
from harness.tools.client import ClientToolService
from harness.web.agent import CLIENT_TOOLS, build_agent
from harness.web.logs import configure_logging
from harness.web.routes.approvals import build_router as build_approvals_router
from harness.web.routes.client import build_router as build_client_router
from harness.web.routes.compact import build_router as build_compact_router
from harness.web.routes.mcp import build_router as build_mcp_router
from harness.web.routes.skills import build_router as build_skills_router

logger = logging.getLogger("harness.web")


def build_store(settings: Settings) -> SessionService:
    """The session service over the configured storage backend."""
    return SessionService(JsonlSessionRepository(settings.sessions.root))


def build_mcp(settings: Settings) -> McpServerStore:
    """Connections to whatever `config.json` declares under `mcp.servers`."""
    return McpServerStore(settings.mcp.servers)


def build_channels(
    settings: Settings,
    sessions: SessionService,
    runs: RunStore,
    skills: SkillService,
    client_tools: ClientToolService,
) -> tuple[ChannelGateway, WebChannel]:
    """The gateway, and a runtime per configured platform."""
    chats = JsonlChatRepository(settings.sessions.root.parent / "chats")
    gateway = ChannelGateway(
        chats,
        runs,
        sessions,
        skills,
        public_url=settings.web.public_url,
        client_tools=client_tools.awaited,
    )
    chat_answers = ChatAnswers(chats, sessions, gateway, client_tools)

    web = WebChannel(sessions, runs, gateway)
    gateway.register(web)

    if settings.telegram.bot_token.strip():
        gateway.register(TelegramChannel(settings.telegram.bot_token, gateway, chat_answers))

    if settings.discord.bot_token.strip():
        gateway.register(DiscordChannel(settings.discord.bot_token, gateway))

    return gateway, web


def _resolve_context_tokens(settings: Settings) -> int | None:
    """The compaction window: the configured cap, the endpoint's report, or `None`."""
    configured = settings.compaction.context_tokens
    if configured is not None:
        logger.info("compaction: context window %d tokens (from config)", configured)
        return configured
    discovered = asyncio.run(context_length(settings.llm))
    if discovered is not None:
        logger.info("compaction: context window %d tokens (reported by endpoint)", discovered)
    else:
        logger.warning(
            "compaction: context window unknown — no config value and the endpoint did not "
            "report one; automatic compaction is off, only a provider overflow triggers it"
        )
    return discovered


def create_web_app() -> FastAPI:
    """The application uvicorn starts."""
    configure_logging()
    settings = load()
    service = build_store(settings)
    mcp = build_mcp(settings)
    skills = SkillService(settings.skills)
    gate = ApprovalGate(frozenset(settings.approval.tools), settings.approval.grants_path)
    client_tools = ClientToolService(CLIENT_TOOLS, gate)
    context_tokens = _resolve_context_tokens(settings)
    runs = RunStore(
        service, build_agent(settings, service, mcp, skills, client_tools, gate, context_tokens)
    )
    gateway, web = build_channels(settings, service, runs, skills, client_tools)
    return create_app(runs, gateway, web, mcp, skills, client_tools, gate)


def create_app(
    runs: RunStore,
    gateway: ChannelGateway,
    web: WebChannel,
    mcp: McpServerStore,
    skills: SkillService,
    client_tools: ClientToolService,
    gate: ApprovalGate,
) -> FastAPI:
    """The HTTP surface, mounted from the channel that owns it."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await mcp.start()
        await gateway.start()
        yield
        await gateway.aclose()
        await runs.aclose()
        await mcp.aclose()

    app = FastAPI(title="cell-harness", lifespan=lifespan)
    app.include_router(web.router)
    app.include_router(build_skills_router(skills))
    app.include_router(build_mcp_router(mcp))
    app.include_router(build_client_router(web, client_tools))
    app.include_router(build_approvals_router(gate))
    app.include_router(build_compact_router(web))
    return app
