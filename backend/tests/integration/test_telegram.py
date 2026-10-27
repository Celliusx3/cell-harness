"""The channel wired into the app, end to end."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import httpx
from pydantic import SecretStr

from harness.bots import ASSISTANT_ID
from harness.channels.gateway import ChannelGateway
from harness.channels.protocol import InboundMessage
from harness.channels.repositories.jsonl import JsonlChatRepository
from harness.config.settings import Settings
from harness.runs.bot_messages import BotMessages
from harness.runs.service import RunService
from harness.runtime.service import Runtime
from harness.secrets import Destination, SecretService
from harness.secrets.models.details import TelegramDetails
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.web.server import build_channels, create_app
from tests.unit.fakes import OneModel, ScriptedClient, completed
from tests.unit.helpers import client_tools, link_to_assistant, no_approvals, no_bots, no_skills
from tests.unit.telegram_fakes import telegram_channel
from tests.webapp import channel_services, channels_of, secrets_in, web_gateway, web_mcp

CHAT = "909"


def build(tmp_path):
    ids = iter(f"c{n}" for n in range(100))
    sessions = SessionService(
        JsonlSessionRepository(tmp_path / "sessions"),
        now=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        new_id=lambda: next(ids),
    )
    runtime = Runtime(
        models=OneModel(ScriptedClient(completed("the answer"))),
        images=None,
        checkpoint=sessions.flush,
    )
    runs = RunService(sessions, runtime, no_bots(sessions))
    tools = client_tools()
    gateway, web = web_gateway(tmp_path, sessions, runs, skills=no_skills())
    channel, bot = telegram_channel(gateway)
    gateway.register(channel)
    app = create_app(
        runs,
        channels_of(gateway, web, secrets_in(tmp_path)),
        web_mcp(),
        no_skills(),
        tools,
        no_approvals(),
        no_bots(sessions),
        secrets_in(tmp_path),
        BotMessages(sessions, no_bots(sessions), runs),
    )
    return bot, app, gateway, runs, sessions


async def settle(runs: RunService, gateway: ChannelGateway) -> None:
    """Wait for the turn and its delivery to finish."""
    for _ in range(300):
        task = gateway._tasks.get(("telegram", CHAT))
        busy = task is not None and not task.done()
        if not busy and not any(runs._runs.values()):
            return
        await asyncio.sleep(0.01)
    raise AssertionError("channel never went idle")


async def until(predicate, *, what: str) -> None:
    """Wait for something to *start* happening."""
    for _ in range(400):
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"timed out waiting for {what}")


class RecordingChannel:
    """A channel-shaped stub, to assert the app's wiring rather than PTB's."""

    channel = "recording"

    def __init__(self) -> None:
        self.running = False

    async def run(self) -> None:
        self.running = True
        await asyncio.Event().wait()

    async def send_message(self, chat_id: str, text: str) -> None: ...

    async def send_typing(self, chat_id: str) -> None: ...


async def test_the_lifespan_starts_and_stops_the_gateway(tmp_path) -> None:
    bot, app, gateway, runs, sessions = build(tmp_path)
    recording = RecordingChannel()
    gateway.register(recording)

    async with app.router.lifespan_context(app):
        await until(lambda: recording.running, what="the channel to start")

    assert gateway.channels == ["web", "telegram", "recording"]


async def test_an_app_with_only_the_browser_still_serves(tmp_path) -> None:
    sessions = SessionService(JsonlSessionRepository(tmp_path / "sessions"))
    runs = RunService(
        sessions, Runtime(models=OneModel(ScriptedClient([])), images=None), no_bots(sessions)
    )
    tools = client_tools()
    gateway, web = web_gateway(tmp_path, sessions, runs, skills=no_skills())
    wired = create_app(
        runs,
        channels_of(gateway, web, secrets_in(tmp_path)),
        web_mcp(),
        no_skills(),
        tools,
        no_approvals(),
        no_bots(sessions),
        secrets_in(tmp_path),
        BotMessages(sessions, no_bots(sessions), runs),
    )

    assert gateway.channels == ["web"]
    async with wired.router.lifespan_context(wired):
        pass


async def test_a_message_lands_in_assistants_chat_visible_over_http(tmp_path) -> None:
    bot, app, gateway, runs, sessions = build(tmp_path)
    await link_to_assistant(JsonlChatRepository(tmp_path / "chats"), "telegram", CHAT)

    await gateway.receive(InboundMessage(channel="telegram", chat_id=CHAT, text="hello there"))
    await settle(runs, gateway)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://harness.test"
    ) as http:
        detail = (await http.get(f"/api/conversations/{ASSISTANT_ID}")).json()

    prompts = [e["message"]["content"] for e in detail["events"] if e["type"] == "user/message"]
    assert prompts == ["hello there"]
    assert bot.sent == [(CHAT, "the answer")]


async def test_a_browser_reply_lands_in_assistants_chat_beside_telegrams(tmp_path) -> None:
    bot, app, gateway, runs, sessions = build(tmp_path)
    await link_to_assistant(JsonlChatRepository(tmp_path / "chats"), "telegram", CHAT)
    await gateway.receive(InboundMessage(channel="telegram", chat_id=CHAT, text="from my phone"))
    await settle(runs, gateway)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://harness.test"
    ) as http:
        sent = await http.post(
            f"/api/conversations/{ASSISTANT_ID}/messages",
            json={"prompt": "from the browser"},
        )
        assert sent.status_code == 202
        await settle(runs, gateway)
        detail = (await http.get(f"/api/conversations/{ASSISTANT_ID}")).json()

    prompts = [e["message"]["content"] for e in detail["events"] if e["type"] == "user/message"]
    assert prompts == ["from my phone", "from the browser"]
    assert bot.sent == [(CHAT, "the answer")]


async def _channels(tmp_path: Path, keyring: SecretService) -> ChannelGateway:
    """The gateway once the saved tokens are registered on it, with nothing started."""
    sessions = SessionService(JsonlSessionRepository(tmp_path / "sessions"))
    runs = RunService(
        sessions, Runtime(models=OneModel(ScriptedClient([])), images=None), no_bots(sessions)
    )
    settings = Settings(local_settings_path=tmp_path / "config.local.json")
    channels = build_channels(settings, channel_services(tmp_path, sessions, runs), keyring)
    await channels.platforms.start_saved()
    return channels.gateway


async def test_no_token_means_no_channel(tmp_path) -> None:
    assert (await _channels(tmp_path, secrets_in(tmp_path))).channels == ["web"]


async def test_a_custom_key_named_telegram_is_not_a_token(tmp_path) -> None:
    keyring = secrets_in(tmp_path)
    site = Destination(origin="https://telegram.example", auth="bearer")
    keyring.save("telegram", site, SecretStr("custom-key-not-a-token"))

    assert (await _channels(tmp_path, keyring)).channels == ["web"]


async def test_a_token_builds_a_channel(tmp_path) -> None:
    keyring = secrets_in(tmp_path)
    keyring.add_credential("telegram", TelegramDetails(), SecretStr("123:abc-telegram"))

    built = await _channels(tmp_path, keyring)

    assert built.channels == ["web", "telegram"]
    await built.aclose()
