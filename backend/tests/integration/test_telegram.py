"""The channel wired into the app, end to end."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx

from harness.agent.service import LoopAgent
from harness.bots import ASSISTANT_ID
from harness.channels.gateway import ChannelGateway
from harness.channels.protocol import InboundMessage
from harness.config.settings import Settings
from harness.runs.store import RunStore
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.web.server import build_channels, create_app
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import client_tools, no_bots, no_gate, no_skills
from tests.unit.telegram_fakes import telegram_channel
from tests.webapp import web_gateway, web_mcp

CHAT = "909"


def build(tmp_path):
    ids = iter(f"c{n}" for n in range(100))
    sessions = SessionService(
        JsonlSessionRepository(tmp_path / "sessions"),
        now=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        new_id=lambda: next(ids),
    )
    agent = LoopAgent(
        model="m",
        client=ScriptedClient(completed("the answer")),
        checkpoint=sessions.flush,
    )
    runs = RunStore(sessions, agent, no_bots(sessions))
    tools = client_tools()
    gateway, web = web_gateway(tmp_path, sessions, runs, skills=no_skills())
    channel, bot = telegram_channel(gateway)
    gateway.register(channel)
    app = create_app(
        runs, gateway, web, web_mcp(), no_skills(), tools, no_gate(), no_bots(sessions)
    )
    return bot, app, gateway, runs, sessions


async def settle(runs: RunStore, gateway: ChannelGateway) -> None:
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
    runs = RunStore(sessions, LoopAgent(model="m", client=ScriptedClient([])), no_bots(sessions))
    tools = client_tools()
    gateway, web = web_gateway(tmp_path, sessions, runs, skills=no_skills())
    wired = create_app(
        runs, gateway, web, web_mcp(), no_skills(), tools, no_gate(), no_bots(sessions)
    )

    assert gateway.channels == ["web"]
    async with wired.router.lifespan_context(wired):
        pass


async def test_a_message_lands_in_assistants_chat_visible_over_http(tmp_path) -> None:
    bot, app, gateway, runs, sessions = build(tmp_path)

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


async def test_no_token_means_no_channel(tmp_path) -> None:
    sessions = SessionService(JsonlSessionRepository(tmp_path / "sessions"))
    runs = RunStore(sessions, LoopAgent(model="m", client=ScriptedClient([])), no_bots(sessions))
    settings = Settings(telegram={"bot_token": ""}, discord={"bot_token": ""})

    assert build_channels(settings, sessions, runs, no_skills(), client_tools(), no_bots(sessions))[
        0
    ].channels == ["web"]


async def test_a_whitespace_token_is_not_a_token(tmp_path) -> None:
    sessions = SessionService(JsonlSessionRepository(tmp_path / "sessions"))
    runs = RunStore(sessions, LoopAgent(model="m", client=ScriptedClient([])), no_bots(sessions))

    settings = Settings(telegram={"bot_token": "   "}, discord={"bot_token": ""})

    assert build_channels(settings, sessions, runs, no_skills(), client_tools(), no_bots(sessions))[
        0
    ].channels == ["web"]


async def test_a_token_builds_a_channel(tmp_path) -> None:
    sessions = SessionService(JsonlSessionRepository(tmp_path / "sessions"))
    runs = RunStore(sessions, LoopAgent(model="m", client=ScriptedClient([])), no_bots(sessions))
    settings = Settings(telegram={"bot_token": "123:abc"}, discord={"bot_token": ""})

    built, _ = build_channels(
        settings, sessions, runs, no_skills(), client_tools(), no_bots(sessions)
    )

    assert built.channels == ["web", "telegram"]
    await built.aclose()
