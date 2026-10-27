"""The composition root, and the ASGI application."""

from __future__ import annotations

import functools
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI

from harness.bots import BotService
from harness.channels.client import ChatAnswers
from harness.channels.gateway import ChannelGateway
from harness.channels.repositories.jsonl import JsonlChatRepository
from harness.channels.web.channel import WebChannel
from harness.config.settings import Settings, load
from harness.files import ChatFileService, DiskChatFileRepository
from harness.images import BLOBS, DiskImageRepository, ImageService
from harness.llm.adapters import context_window_tokens
from harness.mcp.relay import Relays
from harness.mcp.service import McpService
from harness.prompts import ASSISTANT_INSTRUCTIONS
from harness.runs.bot_messages import BotMessages
from harness.runs.service import RunService
from harness.secrets import (
    DEFAULT_MODEL_CREDENTIAL,
    DiskSecretRepository,
    SecretNotFound,
    SecretService,
)
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.skills import SkillService
from harness.tools import ApprovalService
from harness.tools.client import ClientToolService
from harness.web.bot_models import llm_settings_for
from harness.web.errors import exception_handlers
from harness.web.file_keys import move_file_keys, require_default_model
from harness.web.logs import configure_logging
from harness.web.platforms import PlatformChannels, platform_channel
from harness.web.routes.approvals import build_router as build_approvals_router
from harness.web.routes.bots import build_router as build_bots_router
from harness.web.routes.client import build_router as build_client_router
from harness.web.routes.compact import build_router as build_compact_router
from harness.web.routes.credentials import build_router as build_credentials_router
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


def build_keyring(settings: Settings) -> SecretService:
    """The keyring, once the settings file's keys are moved in; refused with no Default model."""
    keyring = SecretService(
        DiskSecretRepository(settings.secrets.path),
        encryption_key=settings.secrets.encryption_key,
    )
    move_file_keys(settings.local_settings_path, settings.llm, keyring)
    require_default_model(keyring, settings.local_settings_path)
    return keyring


@dataclass(frozen=True)
class ChannelServices:
    """What every channel's chats reach."""

    sessions: SessionService
    runs: RunService
    skills: SkillService
    client_tools: ClientToolService
    bots: BotService
    files: ChatFileService
    images: ImageService


@dataclass(frozen=True)
class Channels:
    """The gateway, the browser's channel on it, and the chat platforms that join and leave it."""

    gateway: ChannelGateway
    web: WebChannel
    platforms: PlatformChannels


def build_channels(
    settings: Settings, services: ChannelServices, keyring: SecretService
) -> Channels:
    """The gateway with the web on it, and the platforms the keyring's tokens will start there."""
    chats = JsonlChatRepository(settings.sessions.root.parent / "chats")
    gateway = ChannelGateway(
        chats, services.runs, services.sessions, services.skills, public_url=settings.web.public_url
    )
    chat_answers = ChatAnswers(chats, services.sessions, gateway, services.client_tools)

    web = WebChannel(gateway, services.bots, services.files, services.images)
    gateway.register(web)

    make_channel = functools.partial(platform_channel, gateway, chat_answers)
    return Channels(gateway, web, PlatformChannels(gateway, keyring, make_channel))


def _resolve_context_tokens(settings: Settings, keyring: SecretService) -> int | None:
    """The compaction window: the configured cap, the Default model endpoint's report, or `None`."""
    configured = settings.compaction.context_tokens
    if configured is not None:
        logger.info("compaction: context window %d tokens (from config)", configured)
        return configured
    default = keyring.model_credential_named(DEFAULT_MODEL_CREDENTIAL)
    if default is None:
        raise SecretNotFound(DEFAULT_MODEL_CREDENTIAL)
    discovered = context_window_tokens(llm_settings_for(default, settings.llm))
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
    secrets = build_keyring(settings)
    service = build_store(settings)
    disk = DiskChatFileRepository(settings.files.root)
    disk.create_root()
    files = ChatFileService(disk, max_bytes=settings.files.max_bytes)
    images = ImageService(DiskImageRepository(settings.sessions.root / BLOBS))
    mcp = build_mcp(settings)
    skills = SkillService(settings.skills)
    approvals = ApprovalService(
        frozenset(settings.approval.tools), mcp.writing_tool_names, settings.approval.grants_path
    )
    client_tools = ClientToolService(CLIENT_TOOLS, approvals)
    context_tokens = _resolve_context_tokens(settings, secrets)
    bots = BotService(settings.bots.path, service, assistant_instructions=ASSISTANT_INSTRUCTIONS)
    runtime = build_runtime(
        settings,
        service,
        mcp,
        skills,
        client_tools,
        approvals,
        context_tokens,
        bots=bots,
        subagent_logs=build_subagent_logs(settings),
        secrets=secrets,
        images=images,
        files=files,
    )
    runs = RunService(service, runtime, bots)
    assert runtime.tools is not None
    messages = attach_bot_messages(runtime.tools.tool_service, service, bots, runs)
    channels = build_channels(
        settings, ChannelServices(service, runs, skills, client_tools, bots, files, images), secrets
    )
    return create_app(runs, channels, mcp, skills, client_tools, approvals, bots, secrets, messages)


def create_app(
    runs: RunService,
    channels: Channels,
    mcp: McpService,
    skills: SkillService,
    client_tools: ClientToolService,
    approvals: ApprovalService,
    bots: BotService,
    secrets: SecretService,
    messages: BotMessages,
) -> FastAPI:
    """The HTTP surface, mounted from the channel that owns it."""

    gateway, web = channels.gateway, channels.web

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await mcp.start()
        await channels.platforms.start_saved()
        await gateway.start()
        yield
        await gateway.aclose()
        await messages.aclose()
        await runs.aclose()
        await mcp.aclose()

    relays = Relays(now=time.monotonic)
    app = FastAPI(title="cell-harness", lifespan=lifespan, exception_handlers=exception_handlers())
    app.include_router(web.router)
    app.include_router(build_skills_router(skills))
    app.include_router(build_mcp_router(mcp, relays))
    app.include_router(build_relay_router(relays))
    app.include_router(build_client_router(web, client_tools))
    app.include_router(build_secret_card_router(web, client_tools, secrets))
    app.include_router(build_secrets_router(secrets, bots))
    app.include_router(build_credentials_router(secrets, bots, channels.platforms))
    app.include_router(build_approvals_router(approvals))
    app.include_router(build_compact_router(web))
    app.include_router(build_bots_router(bots, runs, secrets))
    app.include_router(build_groups_router(bots))
    return app
