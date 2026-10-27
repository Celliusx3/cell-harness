"""Which saves restart a chat platform's channel: a new token does, nothing else does."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from harness.bots import ASSISTANT_ID, BotService
from harness.channels.gateway import ChannelGateway
from harness.channels.repositories.jsonl import JsonlChatRepository
from harness.secrets import DiskSecretRepository, SecretRefused, SecretService
from harness.secrets.models.details import ChatPlatform, DiscordDetails, TelegramDetails
from harness.web.platforms import PlatformChannels
from harness.web.routes.credentials import build_router
from tests.unit.fakes import ScriptedClient
from tests.unit.helpers import durable_service, no_skills, run_service

KEY = "0123456789abcdef0123456789abcdef"
PAGE = "http://127.0.0.1:4887"
TELEGRAM_TOKEN = "123456:AAtelegram-token-1111"
DISCORD_TOKEN = "discord-token-2222"
WAIT_SECONDS = 1.0
GITHUB = {
    "name": "github",
    "details": {
        "kind": "custom",
        "destination": {"origin": "https://api.github.com", "auth": "bearer"},
    },
    "value": "ghp-key-3333",
    "bot_ids": [ASSISTANT_ID],
}
MODEL = {
    "name": "trader_model",
    "details": {"kind": "llm", "base_url": "https://api.example.com/v1", "model": "big"},
    "value": "sk-model-4444",
    "bot_ids": [],
}


class ParkedChannel:
    """A platform that receives nothing and waits until it is stopped."""

    def __init__(self, platform: ChatPlatform) -> None:
        self._platform = platform
        self.began = asyncio.Event()
        self.stopped = asyncio.Event()

    @property
    def channel(self) -> str:
        return self._platform

    def conversation_for(self, chat_id: str) -> str:
        return ASSISTANT_ID

    async def run(self) -> None:
        self.began.set()
        try:
            await asyncio.Event().wait()
        finally:
            self.stopped.set()


class Started:
    """Each channel the platforms were asked to make, in order."""

    def __init__(self) -> None:
        self.channels: list[ParkedChannel] = []

    def __call__(self, platform: ChatPlatform, token: SecretStr) -> ParkedChannel:
        self.channels.append(ParkedChannel(platform))
        return self.channels[-1]

    def of(self, platform: ChatPlatform) -> list[ParkedChannel]:
        return [channel for channel in self.channels if channel.channel == platform]

    async def all_began(self) -> None:
        for channel in self.channels:
            await asyncio.wait_for(channel.began.wait(), WAIT_SECONDS)


@pytest.fixture
def keyring(tmp_path: Path) -> SecretService:
    return SecretService(DiskSecretRepository(tmp_path / "secrets.json"), encryption_key=KEY)


@pytest.fixture
async def gateway(tmp_path: Path) -> AsyncIterator[ChannelGateway]:
    sessions = durable_service(tmp_path / "sessions")
    chats = JsonlChatRepository(tmp_path / "chats")
    gateway = ChannelGateway(
        chats, run_service(sessions, ScriptedClient([])), sessions, no_skills(), public_url="t"
    )
    await gateway.start()
    yield gateway
    await gateway.aclose()


@pytest.fixture
def started() -> Started:
    return Started()


@pytest.fixture
def http(tmp_path: Path, keyring, gateway, started) -> httpx.AsyncClient:
    bots = BotService(
        tmp_path / "bots.json", durable_service(tmp_path / "bots"), assistant_instructions="Hi."
    )
    app = FastAPI()
    app.include_router(build_router(keyring, bots, PlatformChannels(gateway, keyring, started)))
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 50000))
    return httpx.AsyncClient(
        transport=transport, base_url="http://127.0.0.1:4886", headers={"origin": PAGE}
    )


def _platform(kind: ChatPlatform, value: str) -> dict:
    return {"name": kind, "details": {"kind": kind}, "value": value, "bot_ids": []}


async def test_an_edit_that_keeps_the_token_restarts_nothing(http, started) -> None:
    async with http:
        await http.post("/api/credentials", json=_platform("telegram", TELEGRAM_TOKEN))
        await started.all_began()
        kept = {"details": {"kind": "telegram"}, "value": None, "bot_ids": []}
        response = await http.patch("/api/credentials/telegram", json=kept)

    assert response.status_code == 200
    [running] = started.channels
    assert not running.stopped.is_set()


async def test_custom_and_llm_saves_never_restart_a_channel(http, started) -> None:
    async with http:
        await http.post("/api/credentials", json=_platform("discord", DISCORD_TOKEN))
        await started.all_began()
        await http.post("/api/credentials", json=GITHUB)
        await http.post("/api/credentials", json=MODEL)
        change = {"details": MODEL["details"], "value": "sk-model-5555", "bot_ids": []}
        await http.patch("/api/credentials/trader_model", json=change)
        removed = await http.delete("/api/credentials/github")

    assert removed.status_code == 204
    [running] = started.channels
    assert not running.stopped.is_set()


async def test_removing_discord_stops_discord_alone(http, started, gateway) -> None:
    async with http:
        await http.post("/api/credentials", json=_platform("telegram", TELEGRAM_TOKEN))
        await http.post("/api/credentials", json=_platform("discord", DISCORD_TOKEN))
        await started.all_began()
        removed = await http.delete("/api/credentials/discord")

    assert removed.status_code == 204
    assert [channel.stopped.is_set() for channel in started.channels] == [False, True]
    assert gateway.channels == ["telegram"]


async def test_an_edit_that_ticks_bots_for_a_platform_is_refused(http, started) -> None:
    async with http:
        await http.post("/api/credentials", json=_platform("telegram", TELEGRAM_TOKEN))
        change = {"details": {"kind": "telegram"}, "value": None, "bot_ids": [ASSISTANT_ID]}
        response = await http.patch("/api/credentials/telegram", json=change)

    assert response.status_code == 422
    assert ASSISTANT_ID not in response.text
    assert len(started.of("telegram")) == 1


def test_the_keyring_holds_one_credential_per_platform(keyring) -> None:
    keyring.add_credential("discord", DiscordDetails(), SecretStr(DISCORD_TOKEN))
    keyring.add_credential("telegram", TelegramDetails(), SecretStr(TELEGRAM_TOKEN))

    with pytest.raises(SecretRefused, match="already saved as 'discord'"):
        keyring.add_credential("second_bot", DiscordDetails(), SecretStr("discord-token-6666"))
