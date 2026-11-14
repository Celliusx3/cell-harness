"""The composition root, and the ASGI application."""

from __future__ import annotations

import dataclasses
import functools
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import FastAPI

from harness.app_events import AppEventService
from harness.app_events.router.app_event_router import AppEventRouter
from harness.bots import BotRepository, BotService, GroupService
from harness.bots.router.bot_router import BotRouter
from harness.bots.router.group_router import GroupRouter
from harness.bots.service.bot_lifecycle_service import BotLifecycleService
from harness.channels.repository.chat_repository import ChatRepository
from harness.channels.repository.json_chat_repository import JsonChatRepository
from harness.channels.router.link_code_router import LinkCodeRouter
from harness.channels.service.chat_answers import ChatAnswers
from harness.channels.service.gateway import ChannelGateway
from harness.channels.service.inbox import ChatInbox
from harness.channels.service.links import ChatLinks, LinkCodes
from harness.channels.service.platforms import PlatformChannels, PlatformChats, platform_channel
from harness.channels.web.channel import WebChannel
from harness.channels.web.client_router import ClientToolRouter
from harness.channels.web.compact_router import CompactRouter
from harness.channels.web.secret_card_router import SecretCardRouter
from harness.config.settings import Settings, load_settings
from harness.files import ChatFileService, DiskChatFileRepository
from harness.images import BLOBS, DiskImageRepository, ImageService
from harness.mcp import DiskSavedServerRepository, McpService, SavedServerService
from harness.mcp.router.mcp_router import McpRouter
from harness.mcp.router.server_router import ServerRouter
from harness.prompts import ASSISTANT_INSTRUCTIONS
from harness.relay import RelayService
from harness.relay.router.relay_router import RelayRouter
from harness.runs.service.bot_messages import BotMessenger
from harness.runs.service.run_service import RunService
from harness.schedules import Scheduler, ScheduleRepository, ScheduleService
from harness.schedules.router.schedule_router import ScheduleRouter
from harness.secrets import DiskSecretRepository, SecretService
from harness.secrets.router.credential_router import CredentialRouter
from harness.secrets.router.secret_router import SecretRouter
from harness.secrets.service.credential_effects import CredentialEffects
from harness.session.repository.jsonl_session_repository import JsonlSessionRepository
from harness.session.service.session_service import SessionService
from harness.skills import SkillService
from harness.skills.router.skill_router import SkillRouter
from harness.tickets.repository.ticket_repository import TicketRepository
from harness.tickets.router.file_router import TicketFileRouter
from harness.tickets.router.ticket_router import TicketRouter
from harness.tickets.service.ticket_service import TicketService
from harness.tools import ApprovalService
from harness.tools.client import ClientToolService
from harness.tools.router.approval_router import ApprovalRouter
from harness.web.http.errors import exception_handlers
from harness.web.http.logs import configure_logging
from harness.web.runtime import (
    CLIENT_TOOLS,
    attach_bot_messages,
    attach_schedules,
    build_runtime,
)
from harness.web.tickets_wiring import attach_tickets, ticket_workers


def build_sessions(settings: Settings) -> SessionService:
    """The session service over the configured storage backend."""
    return SessionService(JsonlSessionRepository(settings.sessions.root))


def build_subagent_logs(settings: Settings) -> SessionService:
    """The subagents' own logs, beside the conversations and never among them."""
    return SessionService(JsonlSessionRepository(settings.sessions.root.parent / "subagents"))


def build_chats(settings: Settings) -> JsonChatRepository:
    """Every chat's state, beside the conversations."""
    return JsonChatRepository(settings.sessions.root.parent / "chats")


def build_saved_servers(settings: Settings) -> SavedServerService:
    """Every MCP server, as the person added it on the MCP servers screen, kept in `mcp.path`."""
    return SavedServerService(DiskSavedServerRepository(settings.mcp.path))


def build_mcp(saved: SavedServerService) -> McpService:
    """Connections to the person's saved servers, with their keys."""
    return McpService({server.id: server.mcp_server() for server in saved.servers()})


def build_keyring(settings: Settings) -> SecretService:
    """The keyring, where every key the app holds is saved from Credentials."""
    return SecretService(
        DiskSecretRepository(settings.secrets.path),
        encryption_key=settings.secrets.encryption_key,
    )


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
    chats: ChatRepository


@dataclass(frozen=True)
class Channels:
    """The gateway, the browser's channel on it, the chat platforms, and the codes linking them."""

    gateway: ChannelGateway
    web: WebChannel
    platforms: PlatformChannels
    link_codes: LinkCodes


def build_channels(
    settings: Settings, services: ChannelServices, keyring: SecretService
) -> Channels:
    """The gateway with the web on it, and the platforms the keyring's tokens will start there."""
    chats = services.chats
    gateway = ChannelGateway(
        chats, services.runs, services.sessions, services.skills, public_url=settings.web.public_url
    )
    chat_answers = ChatAnswers(chats, services.sessions, gateway, services.client_tools)
    link_codes = LinkCodes(time.monotonic)
    links = ChatLinks(chats, link_codes, services.bots)

    web = WebChannel(gateway, services.bots, services.files, services.images)
    gateway.register(web)

    make_channel = functools.partial(platform_channel, PlatformChats(gateway, chat_answers, links))
    return Channels(gateway, web, PlatformChannels(gateway, keyring, make_channel), link_codes)


def create_web_app() -> FastAPI:
    """The application uvicorn starts."""
    configure_logging()
    settings = load_settings()
    secrets = build_keyring(settings)
    sessions = build_sessions(settings)
    disk = DiskChatFileRepository(settings.files.root)
    disk.create_root()
    files = ChatFileService(disk, max_bytes=settings.files.max_bytes)
    images = ImageService(DiskImageRepository(settings.sessions.root / BLOBS))
    saved_servers = build_saved_servers(settings)
    mcp = build_mcp(saved_servers)
    skills = SkillService(settings.skills)
    approvals = ApprovalService(
        frozenset(settings.approval.tools),
        mcp.writing_tool_names,
        settings.approval.grants_path,
        default_mode=settings.approval.default_mode,
    )
    client_tools = ClientToolService(CLIENT_TOOLS, approvals)
    app_events = AppEventService()
    bots = BotService(
        BotRepository(settings.bots.path),
        sessions,
        assistant_instructions=ASSISTANT_INSTRUCTIONS,
        app_events=app_events,
    )
    subagent_logs = build_subagent_logs(settings)
    chats = build_chats(settings)
    runtime = build_runtime(
        settings,
        sessions,
        mcp,
        skills,
        client_tools,
        approvals,
        bots=bots,
        subagent_logs=subagent_logs,
        secrets=secrets,
        images=images,
        files=files,
    )
    runtime = dataclasses.replace(runtime, inbox=ChatInbox(chats, skills))
    runs = RunService(
        sessions,
        runtime,
        bots,
        GroupService(bots, sessions),
        app_events=app_events,
    )
    assert runtime.tools is not None
    channels = build_channels(
        settings,
        ChannelServices(sessions, runs, skills, client_tools, bots, files, images, chats),
        secrets,
    )
    messages = attach_bot_messages(
        runtime.tools.tool_service, bots, runs, follow=channels.gateway.follow
    )
    now = functools.partial(datetime.now, UTC)
    tool_service = runtime.tools.tool_service
    tickets = TicketService(
        TicketRepository(settings.tickets.path),
        bots,
        runs,
        worker=ticket_workers(tool_service, runtime, subagent_logs, bots.chat_of),
        logs=subagent_logs,
        follow=channels.gateway.follow,
        now=now,
        ids=lambda: uuid.uuid4().hex,
    )
    attach_tickets(tool_service, tickets)
    schedules = ScheduleService(ScheduleRepository(settings.schedules.path), now=now)
    attach_schedules(runtime.tools.tool_service, runs.groups, schedules)
    scheduler = Scheduler(schedules, bots, runs, follow=channels.gateway.follow, now=now)
    return create_app(
        runs,
        channels,
        mcp,
        saved_servers,
        skills,
        client_tools,
        approvals,
        bots,
        secrets,
        messages,
        tickets,
        schedules,
        scheduler,
    )


def create_app(
    runs: RunService,
    channels: Channels,
    mcp: McpService,
    saved_servers: SavedServerService,
    skills: SkillService,
    client_tools: ClientToolService,
    approvals: ApprovalService,
    bots: BotService,
    secrets: SecretService,
    messages: BotMessenger,
    tickets: TicketService,
    schedules: ScheduleService,
    scheduler: Scheduler,
) -> FastAPI:
    """The HTTP surface, mounted from the channel that owns it."""

    gateway, web = channels.gateway, channels.web

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await mcp.start()
        await channels.platforms.start_saved()
        await gateway.start()
        scheduler.start()
        tickets.recover()
        yield
        await gateway.aclose()
        await scheduler.aclose()
        await messages.aclose()
        await tickets.aclose()
        await runs.aclose()
        await mcp.aclose()

    relays = RelayService(now=time.monotonic)
    app = FastAPI(title="cell-harness", lifespan=lifespan, exception_handlers=exception_handlers())
    app.include_router(web.router)
    app.include_router(AppEventRouter(runs.app_events).router)
    app.include_router(SkillRouter(skills).router)
    app.include_router(ServerRouter(mcp, saved_servers).router)
    app.include_router(McpRouter(mcp, relays).router)
    app.include_router(RelayRouter(relays).router)
    app.include_router(ClientToolRouter(web, client_tools).router)
    effects = CredentialEffects(bots, channels.platforms)
    app.include_router(SecretCardRouter(web, client_tools, secrets, effects).router)
    app.include_router(SecretRouter(secrets, bots).router)
    app.include_router(CredentialRouter(secrets, bots, channels.platforms).router)
    app.include_router(ApprovalRouter(approvals).router)
    app.include_router(CompactRouter(web).router)
    app.include_router(BotRouter(bots, BotLifecycleService(bots, runs, secrets, schedules)).router)
    app.include_router(ScheduleRouter(bots, schedules, scheduler, runs).router)
    app.include_router(TicketRouter(tickets, secrets, bots, client_tools).router)
    app.include_router(TicketFileRouter(tickets, web.files, web.images).router)
    app.include_router(GroupRouter(bots, runs.groups).router)
    app.include_router(LinkCodeRouter(channels.link_codes, bots, secrets).router)
    return app
