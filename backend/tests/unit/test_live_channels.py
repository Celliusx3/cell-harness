"""Telegram and Discord start when their credential is saved and stop when it goes."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from harness.bots import ASSISTANT_ID, BotService
from harness.channels.gateway import ChannelGateway
from harness.channels.protocol import InboundMessage
from harness.channels.repositories.jsonl import JsonlChatRepository
from harness.secrets import DiskSecretRepository, SecretService
from harness.secrets.models.details import TelegramDetails
from harness.web.platforms import PlatformChannels
from harness.web.routes.credentials import build_router
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import durable_service, no_skills, run_service

KEY = "0123456789abcdef0123456789abcdef"
PAGE = "http://127.0.0.1:4887"
TOKEN = "123456:AAfirst-telegram-1111"
NEW_TOKEN = "123456:AAsecond-telegram-2222"
WAIT_SECONDS = 1.0


class QueueChannel:
    """A platform that waits until cancelled, and says when it began and when it ended."""

    def __init__(self, name: str = "telegram") -> None:
        self._name = name
        self.running = asyncio.Event()
        self.stopped = asyncio.Event()

    @property
    def channel(self) -> str:
        return self._name

    def conversation_for(self, chat_id: str) -> str:
        return ASSISTANT_ID

    async def run(self) -> None:
        self.running.set()
        try:
            await asyncio.Event().wait()
        finally:
            self.stopped.set()


def _gateway(tmp_path: Path) -> ChannelGateway:
    sessions = durable_service(tmp_path / "sessions")
    runs = run_service(sessions, ScriptedClient(completed("hi")))
    chats = JsonlChatRepository(tmp_path / "chats")
    return ChannelGateway(chats, runs, sessions, no_skills(), public_url="http://t")


async def _began(channel: QueueChannel) -> None:
    await asyncio.wait_for(channel.running.wait(), WAIT_SECONDS)


async def test_a_channel_registered_while_the_gateway_runs_starts_at_once(tmp_path: Path) -> None:
    gateway = _gateway(tmp_path)
    await gateway.start()
    channel = QueueChannel()

    gateway.register(channel)

    await _began(channel)
    await gateway.aclose()


async def test_a_channel_registered_before_start_waits_for_it(tmp_path: Path) -> None:
    gateway = _gateway(tmp_path)
    channel = QueueChannel()
    gateway.register(channel)
    await asyncio.sleep(0)
    assert not channel.running.is_set()

    await gateway.start()

    await _began(channel)
    await gateway.aclose()


async def test_its_disposer_stops_it_and_takes_it_off_the_gateway(tmp_path: Path) -> None:
    gateway = _gateway(tmp_path)
    await gateway.start()
    channel = QueueChannel()
    dispose = gateway.register(channel)
    await _began(channel)

    await dispose()

    assert channel.stopped.is_set()
    assert "telegram" not in gateway.channels
    await dispose()
    await gateway.aclose()


async def test_a_platform_disposed_of_can_register_again(tmp_path: Path) -> None:
    gateway = _gateway(tmp_path)
    await gateway.start()
    dispose = gateway.register(QueueChannel())
    await dispose()
    second = QueueChannel()

    gateway.register(second)

    await _began(second)
    await gateway.aclose()


async def test_a_channel_added_while_running_receives_messages(tmp_path: Path) -> None:
    gateway = _gateway(tmp_path)
    await gateway.start()
    gateway.register(QueueChannel())

    run = await gateway.receive(InboundMessage(channel="telegram", chat_id="1", text="hi"))

    assert run is not None
    await gateway.runs.aclose()
    await gateway.aclose()


@pytest.fixture
def keyring(tmp_path: Path) -> SecretService:
    return SecretService(DiskSecretRepository(tmp_path / "secrets.json"), encryption_key=KEY)


@pytest.fixture
def bots(tmp_path: Path) -> BotService:
    sessions = durable_service(tmp_path / "bot-sessions")
    return BotService(tmp_path / "bots.json", sessions, assistant_instructions="Be kind.")


class ChannelsMade:
    """A channel factory that records each platform and token it was asked to start."""

    def __init__(self) -> None:
        self.started: list[tuple[str, str, QueueChannel]] = []

    def __call__(self, kind: str, token: SecretStr) -> QueueChannel:
        channel = QueueChannel(kind)
        self.started.append((kind, token.get_secret_value(), channel))
        return channel


async def _send(app: FastAPI, method: str, url: str, body: dict | None = None) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 50000))
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:4886") as http:
        return await http.request(method, url, json=body, headers={"origin": PAGE})


def _telegram(name: str, value: str) -> dict:
    return {"name": name, "details": {"kind": "telegram"}, "value": value, "bot_ids": []}


async def _app_with_platforms(
    tmp_path, keyring, bots
) -> tuple[FastAPI, ChannelGateway, list[tuple[str, str, QueueChannel]]]:
    gateway = _gateway(tmp_path)
    factory = ChannelsMade()
    platforms = PlatformChannels(gateway, keyring, factory)
    await gateway.start()
    app = FastAPI()
    app.include_router(build_router(keyring, bots, platforms))
    return app, gateway, factory.started


async def test_saving_a_telegram_token_starts_telegram_and_removing_it_stops_it(
    tmp_path: Path, keyring, bots
) -> None:
    app, gateway, made = await _app_with_platforms(tmp_path, keyring, bots)

    added = await _send(app, "POST", "/api/credentials", _telegram("telegram", TOKEN))
    _, token, first = made[0]
    await _began(first)
    removed = await _send(app, "DELETE", "/api/credentials/telegram")

    assert (added.status_code, removed.status_code) == (201, 204)
    assert token == TOKEN
    assert first.stopped.is_set()
    assert "telegram" not in gateway.channels
    await gateway.aclose()


async def test_a_new_token_restarts_only_that_channel(tmp_path: Path, keyring, bots) -> None:
    app, gateway, made = await _app_with_platforms(tmp_path, keyring, bots)
    discord = {
        "name": "discord",
        "details": {"kind": "discord"},
        "value": "discord-token-3333",
        "bot_ids": [],
    }
    await _send(app, "POST", "/api/credentials", discord)
    await _send(app, "POST", "/api/credentials", _telegram("telegram", TOKEN))

    change = {"details": {"kind": "telegram"}, "value": NEW_TOKEN, "bot_ids": []}
    response = await _send(app, "PATCH", "/api/credentials/telegram", change)

    by_token = {token: channel for _, token, channel in made}
    await _began(by_token[NEW_TOKEN])
    assert response.status_code == 200
    assert by_token[TOKEN].stopped.is_set()
    assert not by_token["discord-token-3333"].stopped.is_set()
    assert len(made) == 3
    await gateway.aclose()


async def test_a_second_telegram_credential_is_refused(tmp_path: Path, keyring, bots) -> None:
    app, gateway, made = await _app_with_platforms(tmp_path, keyring, bots)
    await _send(app, "POST", "/api/credentials", _telegram("telegram", TOKEN))

    response = await _send(app, "POST", "/api/credentials", _telegram("other_telegram", NEW_TOKEN))

    assert response.status_code == 409
    assert len(made) == 1
    await gateway.aclose()


async def test_a_telegram_credential_serves_no_bots(tmp_path: Path, keyring, bots) -> None:
    app, gateway, _ = await _app_with_platforms(tmp_path, keyring, bots)
    body = {**_telegram("telegram", TOKEN), "bot_ids": [ASSISTANT_ID]}

    response = await _send(app, "POST", "/api/credentials", body)

    assert response.status_code == 422
    await gateway.aclose()


async def test_saved_tokens_start_their_channels_on_start(tmp_path: Path, keyring, bots) -> None:
    keyring.add_credential("telegram", TelegramDetails(), SecretStr(TOKEN))
    gateway = _gateway(tmp_path)
    factory = ChannelsMade()
    platforms = PlatformChannels(gateway, keyring, factory)

    await platforms.start_saved()
    await gateway.start()

    await _began(factory.started[0][2])
    assert factory.started[0][1] == TOKEN
    await gateway.aclose()
