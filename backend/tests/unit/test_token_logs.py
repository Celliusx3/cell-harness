"""A refused Telegram or Discord token is said in the logs, and the token never is."""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import discord
import httpx
import pytest
from discord.http import HTTPClient, Route
from telegram.request import HTTPXRequest

from harness.channels.client import ChatAnswers
from harness.channels.discord.channel import DiscordChannel
from harness.channels.gateway import ChannelGateway
from harness.channels.repositories.jsonl import JsonlChatRepository
from harness.channels.telegram.channel import TelegramChannel
from harness.web.logs import keep_token_urls_out
from tests.unit.fakes import ScriptedClient
from tests.unit.helpers import (
    client_tools,
    durable_service,
    no_links,
    no_skills,
    run_service,
    until,
)

TELEGRAM_TOKEN = "123456:AAsecret-telegram-token-7777"
DISCORD_TOKEN = "discord-secret-token-8888"
TELEGRAM_REFUSAL = b'{"ok": false, "error_code": 401, "description": "Unauthorized"}'


def _gateway(tmp_path: Path) -> ChannelGateway:
    sessions = durable_service(tmp_path / "sessions")
    runs = run_service(sessions, ScriptedClient([]))
    chats = JsonlChatRepository(tmp_path / "chats")
    return ChannelGateway(chats, runs, sessions, no_skills(), public_url="http://t")


async def test_a_refused_telegram_token_is_logged_without_the_token(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    caplog.set_level(logging.DEBUG)
    keep_token_urls_out()
    asked: list[str] = []

    async def telegram_refuses(self, url: str, method: str, *args, **kwargs) -> tuple[int, bytes]:
        asked.append(url)
        return 401, TELEGRAM_REFUSAL

    monkeypatch.setattr(HTTPXRequest, "do_request", telegram_refuses)
    gateway = _gateway(tmp_path)
    await gateway.start()
    answers = ChatAnswers(None, None, gateway, client_tools())

    gateway.register(TelegramChannel(TELEGRAM_TOKEN, gateway, answers, no_links()))
    await until(lambda: "telegram channel stopped" in caplog.text, what="the refusal")

    assert [url.rsplit("/", 1)[-1] for url in asked] == ["getMe"]
    assert TELEGRAM_TOKEN in asked[0]
    assert "Telegram refused the bot token" in caplog.text
    assert TELEGRAM_TOKEN not in caplog.text
    await gateway.aclose()


async def test_a_refused_discord_token_is_logged_without_the_token(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    caplog.set_level(logging.DEBUG)
    keep_token_urls_out()
    asked: list[str] = []

    async def discord_refuses(self, route: Route, **kwargs) -> None:
        asked.append(route.path)
        unauthorized = SimpleNamespace(status=401, reason="Unauthorized")
        raise discord.HTTPException(unauthorized, {"code": 0, "message": "401: Unauthorized"})

    monkeypatch.setattr(HTTPClient, "request", discord_refuses)
    gateway = _gateway(tmp_path)
    await gateway.start()

    gateway.register(DiscordChannel(DISCORD_TOKEN, gateway, no_links()))
    await until(lambda: "discord channel stopped" in caplog.text, what="the refusal")

    assert asked == ["/users/@me"]
    assert "Improper token has been passed" in caplog.text
    assert DISCORD_TOKEN not in caplog.text
    await gateway.aclose()


async def test_a_request_url_holding_a_telegram_token_stays_out_of_the_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.NOTSET)
    transport = httpx.MockTransport(lambda request: httpx.Response(401))
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe"
    async with httpx.AsyncClient(transport=transport) as http:
        await http.post(url)
        logged_before = TELEGRAM_TOKEN in caplog.text
        caplog.clear()

        keep_token_urls_out()
        await http.post(url)

    assert logged_before
    assert TELEGRAM_TOKEN not in caplog.text
