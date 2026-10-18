"""The composition root, and the ASGI application."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from harness.bots import BotService
from harness.channels.client import ChatAnswers
from harness.channels.discord.channel import DiscordChannel
from harness.channels.gateway import ChannelGateway
from harness.channels.repositories.jsonl import JsonlChatRepository
from harness.channels.telegram.channel import TelegramChannel
from harness.channels.web.channel import WebChannel
from harness.config.settings import Settings, load
from harness.files import ChatFileService, DiskChatFileRepository
from harness.images import BLOBS, DiskImageRepository, ImageService
from harness.llm.adapters.context_window import context_length
from harness.mcp.relay import Relays
from harness.mcp.service import McpService
from harness.prompts import ASSISTANT_INSTRUCTIONS
from harness.runs.bot_messages import BotMessages
from harness.runs.service import RunService
from harness.secrets import SecretService
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.skills import SkillService
from harness.tools.approval import ApprovalGate
from harness.tools.client import ClientToolService
from harness.web.logs import configure_logging
from harness.web.routes.approvals import build_router as build_approvals_router
from harness.web.routes.bots import build_router as build_bots_router
from harness.web.routes.client import build_router as build_client_router
from harness.web.routes.compact import build_router as build_compact_router
from harness.web.routes.groups import build_router as build_groups_router
from harness.web.routes.mcp import build_router as build_mcp_router
from harness.web.routes.relay import build_router as build_relay_router
from harness.web.routes.secret_card import build_router as build_secret_card_router
from harness.web.routes.secrets import build_router as build_secrets_router
from harness.web.routes.skills import build_router as build_skills_router
from harness.web.runtime import CLIENT_TOOLS, attach_bot_messages, build_runtime

logger = logging.getLogger("harness.web")


def build_store(settings: Settings) -> SessionService:
    """The session service over the configured storage backend."""
    return SessionService(JsonlSessionRepository(settings.sessions.root))


def build_subagent_logs(settings: Settings) -> SessionService:
    """The subagents' own logs, beside the conversations and never among them."""
    return SessionService(JsonlSessionRepository(settings.sessions.root.parent / "subagents"))


def build_mcp(settings: Settings) -> McpService:
    """Connections to whatever `config.json` declares under `mcp.servers`."""
    return McpService(settings.mcp.servers)


def build_channels(
    settings: Settings,
    sessions: SessionService,
    runs: RunService,
    skills: SkillService,
    client_tools: ClientToolService,
    bots: BotService,
    files: ChatFileService,
    images: ImageService,
) -> tuple[ChannelGateway, WebChannel]:
    """The gateway with a channel registered per configured platform, and the web channel."""
    chats = JsonlChatRepository(settings.sessions.root.parent / "chats")
    gateway = ChannelGateway(chats, runs, sessions, skills, public_url=settings.web.public_url)
    chat_answers = ChatAnswers(chats, sessions, gateway, client_tools)

    web = WebChannel(gateway, bots, files, images)
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
    discovered = context_length(settings.llm)
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
    disk = DiskChatFileRepository(settings.files.root)
    disk.create_root()
    files = ChatFileService(disk, max_bytes=settings.files.max_bytes)
    images = ImageService(DiskImageRepository(settings.sessions.root / BLOBS))
    mcp = build_mcp(settings)
    skills = SkillService(settings.skills)
    gate = ApprovalGate(
        frozenset(settings.approval.tools), mcp.writing_tool_names, settings.approval.grants_path
    )
    client_tools = ClientToolService(CLIENT_TOOLS, gate)
    context_tokens = _resolve_context_tokens(settings)
    bots = BotService(settings.bots.path, service, assistant_instructions=ASSISTANT_INSTRUCTIONS)
    secrets = SecretService(settings.secrets.path, encryption_key=settings.secrets.encryption_key)
    runtime = build_runtime(
        settings,
        service,
        mcp,
        skills,
        client_tools,
        gate,
        context_tokens,
        bots=bots,
        subagent_logs=build_subagent_logs(settings),
        secrets=secrets,
        images=images,
        files=files,
    )
    runs = RunService(service, runtime, bots)
    assert runtime.tools is not None
    messages = attach_bot_messages(runtime.tools.registry, service, bots, runs)
    gateway, web = build_channels(
        settings, service, runs, skills, client_tools, bots, files, images
    )
    return create_app(runs, gateway, web, mcp, skills, client_tools, gate, bots, secrets, messages)


def create_app(
    runs: RunService,
    gateway: ChannelGateway,
    web: WebChannel,
    mcp: McpService,
    skills: SkillService,
    client_tools: ClientToolService,
    gate: ApprovalGate,
    bots: BotService,
    secrets: SecretService,
    messages: BotMessages,
) -> FastAPI:
    """The HTTP surface, mounted from the channel that owns it."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await mcp.start()
        await gateway.start()
        yield
        await gateway.aclose()
        await messages.aclose()
        await runs.aclose()
        await mcp.aclose()

    relays = Relays(now=time.monotonic)
    app = FastAPI(title="cell-harness", lifespan=lifespan)
    app.include_router(web.router)
    app.include_router(build_skills_router(skills))
    app.include_router(build_mcp_router(mcp, relays))
    app.include_router(build_relay_router(relays))
    app.include_router(build_client_router(web, client_tools))
    app.include_router(build_secret_card_router(web, client_tools, secrets))
    app.include_router(build_secrets_router(secrets, bots))
    app.include_router(build_approvals_router(gate))
    app.include_router(build_compact_router(web))
    app.include_router(build_bots_router(bots, runs, secrets))
    app.include_router(build_groups_router(bots))
    return app
