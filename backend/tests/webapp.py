"""Building the app the way the server does, for tests that drive HTTP."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI

from harness.bots import BotService
from harness.channels.gateway import ChannelGateway
from harness.channels.repositories.jsonl import JsonlChatRepository
from harness.channels.web.channel import WebChannel
from harness.config.sections import FileSettings, McpServer
from harness.config.settings import Settings
from harness.files import ChatFileService, DiskChatFileRepository
from harness.images import BLOBS, DiskImageRepository, ImageService
from harness.mcp.client import ClientFactory, open_client
from harness.mcp.service import McpService
from harness.prompts import ASSISTANT_INSTRUCTIONS
from harness.runs.bot_messages import BotMessages
from harness.runs.service import RunService
from harness.secrets import DiskSecretRepository, SecretService
from harness.session.service import SessionService
from harness.skills import SkillService
from harness.tools import ApprovalService
from harness.tools.client import ClientToolService
from harness.web.server import create_app
from tests.unit.helpers import client_tools as default_client_tools
from tests.unit.helpers import no_approvals, no_bots
from tests.unit.telegram_fakes import FakeBot, telegram_channel

TEST_ENCRYPTION_KEY = "test-encryption-key"


def startup_settings(tmp_path: Path) -> Settings:
    """Settings that keep all `create_web_app` makes under `tmp_path`, keys as `secrets_in`."""
    return Settings(
        llm={"model": "m", "api_key": "k", "vision": True},
        sessions={"root": tmp_path / "sessions"},
        files={"root": tmp_path / "files"},
        bots={"path": tmp_path / "bots.json"},
        secrets={"path": tmp_path / "secrets.json", "encryption_key": TEST_ENCRYPTION_KEY},
        approval={"grants_path": tmp_path / "approvals.json"},
        skills={"roots": [tmp_path / "skills"], "editable": tmp_path / "skills"},
        compaction={"context_tokens": 1000},
        telegram={"bot_token": ""},
        discord={"bot_token": ""},
        mcp={"servers": {}},
    )


def secrets_in(tmp_path: Path) -> SecretService:
    """Keys a test saves, sealed in a secrets file under `tmp_path`."""
    return SecretService(
        DiskSecretRepository(tmp_path / "secrets.json"), encryption_key=TEST_ENCRYPTION_KEY
    )


def bots_in(tmp_path: Path, service: SessionService) -> BotService:
    """Assistant and any bot a test makes, kept in a bots file under `tmp_path`."""
    return BotService(
        tmp_path / "bots.json", service, assistant_instructions=ASSISTANT_INSTRUCTIONS
    )


def files_in(tmp_path: Path, *, max_bytes: int = FileSettings().max_bytes) -> ChatFileService:
    """Each chat's files, in a folder under `tmp_path`."""
    return ChatFileService(DiskChatFileRepository(tmp_path / "files"), max_bytes=max_bytes)


def images_in(tmp_path: Path) -> ImageService:
    """The images models are shown, beside the conversations kept under `tmp_path / "sessions"`."""
    return ImageService(DiskImageRepository(tmp_path / "sessions" / BLOBS))


def web_gateway(
    tmp_path: Path,
    service: SessionService,
    runs: RunService,
    *,
    skills: SkillService,
    bots: BotService | None = None,
    files: ChatFileService | None = None,
) -> tuple[ChannelGateway, WebChannel]:
    """A gateway with only the browser registered."""
    gateway = ChannelGateway(
        JsonlChatRepository(tmp_path / "chats"),
        runs,
        service,
        skills,
        public_url="http://t",
    )
    web = WebChannel(
        gateway,
        bots or bots_in(tmp_path, service),
        files or files_in(tmp_path),
        images_in(tmp_path),
    )
    gateway.register(web)
    return gateway, web


def web_mcp(
    servers: dict[str, McpServer] | None = None,
    *,
    client_factory: ClientFactory = open_client,
) -> McpService:
    """A service over whatever servers a test declares — none, by default."""
    return McpService(servers or {}, client_factory=client_factory)


def web_app(
    tmp_path: Path,
    service: SessionService,
    runs: RunService,
    *,
    mcp: McpService | None = None,
    skills: SkillService,
    client_tools: ClientToolService | None = None,
    approvals: ApprovalService | None = None,
    bots: BotService | None = None,
    secrets: SecretService | None = None,
    files: ChatFileService | None = None,
) -> FastAPI:
    """The application, wired as `create_web_app` wires it."""
    client_tools = client_tools or default_client_tools()
    bots = bots or bots_in(tmp_path, service)
    gateway, web = web_gateway(tmp_path, service, runs, skills=skills, bots=bots, files=files)
    return create_app(
        runs,
        gateway,
        web,
        mcp or web_mcp(),
        skills,
        client_tools,
        approvals or no_approvals(),
        bots,
        secrets or secrets_in(tmp_path),
        BotMessages(service, bots, runs),
    )


def web_app_with_telegram(
    tmp_path: Path,
    service: SessionService,
    runs: RunService,
    *,
    skills: SkillService,
    client_tools: ClientToolService | None = None,
    approvals: ApprovalService | None = None,
    secrets: SecretService | None = None,
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
        approvals or no_approvals(),
        bots,
        secrets or secrets_in(tmp_path),
        BotMessages(service, bots, runs),
    )
    return app, gateway, bot


async def idle(runs: RunService, gateway: ChannelGateway) -> None:
    """Wait for every turn and every chat's delivery to finish."""
    for _ in range(300):
        if not gateway._tasks.running() and not runs._runs:
            return
        await asyncio.sleep(0.01)
    raise AssertionError("the gateway never went idle")
