"""Telegram and Discord write into Assistant's one chat, the same one the browser shows."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx

from harness.bots import ASSISTANT_ID, BotStore
from harness.channels.gateway import ChannelGateway
from harness.channels.protocol import InboundMessage
from harness.channels.repositories.jsonl import JsonlChatRepository
from harness.llm.client import LLMClient
from harness.llm.messages import Message, ToolSpec
from harness.llm.stream import StreamEvent
from harness.runs.store import RunStore
from harness.runtime.service import Runtime
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.web.server import create_app
from tests.unit.fakes import SteppedClient, completed
from tests.unit.helpers import client_tools, no_gate, no_skills
from tests.unit.telegram_fakes import telegram_channel
from tests.webapp import web_gateway, web_mcp

CHAT = "909"


class HeldClient(SteppedClient):
    """Answers in order, holding the first answer until `release` is set."""

    def __init__(self, release: asyncio.Event, *replies: str) -> None:
        super().__init__(*(completed(reply) for reply in replies))
        self._release = release

    async def stream_completion(
        self, messages: list[Message], model: str, *, tools: list[ToolSpec] | None = None
    ) -> AsyncIterator[StreamEvent]:
        if self.calls == 0:
            await self._release.wait()
        async for event in super().stream_completion(messages, model, tools=tools):
            yield event


def build(tmp_path, *replies: str):
    return build_on(tmp_path, SteppedClient(*(completed(reply) for reply in replies)))


def build_on(tmp_path, model: LLMClient):
    sessions = SessionService(
        JsonlSessionRepository(tmp_path / "sessions"),
        now=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )
    bots = BotStore(tmp_path / "bots.json", sessions, assistant_instructions="ASSISTANT")
    runtime = Runtime(model="m", client=model, checkpoint=sessions.flush)
    runs = RunStore(sessions, runtime, bots)
    gateway, web = web_gateway(tmp_path, sessions, runs, skills=no_skills())
    channel, bot = telegram_channel(gateway)
    gateway.register(channel)
    app = create_app(runs, gateway, web, web_mcp(), no_skills(), client_tools(), no_gate(), bots)
    http = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")
    return bot, http, gateway, runs


async def settle(runs: RunStore, gateway: ChannelGateway) -> None:
    for _ in range(300):
        task = gateway._tasks.get(("telegram", CHAT))
        busy = task is not None and not task.done()
        if not busy and not any(runs._runs.values()):
            return
        await asyncio.sleep(0.01)
    raise AssertionError("channel never went idle")


def _prompts(chat: dict) -> list[str]:
    return [e["message"]["content"] for e in chat["events"] if e["type"] == "user/message"]


async def test_a_telegram_message_lands_in_assistants_chat(tmp_path) -> None:
    bot, http, gateway, runs = build(tmp_path, "the answer")
    async with http:
        await gateway.receive(
            InboundMessage(channel="telegram", chat_id=CHAT, text="from my phone")
        )
        await settle(runs, gateway)
        chat = (await http.get(f"/api/conversations/{ASSISTANT_ID}")).json()

    assert _prompts(chat) == ["from my phone"]
    assert bot.sent == [(CHAT, "the answer")]


async def test_a_browser_turn_is_not_sent_to_telegram(tmp_path) -> None:
    bot, http, gateway, runs = build(tmp_path, "one", "from the web", "three")
    async with http:
        await gateway.receive(InboundMessage(channel="telegram", chat_id=CHAT, text="first"))
        await settle(runs, gateway)
        sent = await http.post(
            f"/api/conversations/{ASSISTANT_ID}/messages", json={"prompt": "in the browser"}
        )
        assert sent.status_code == 202
        await settle(runs, gateway)
        await gateway.receive(InboundMessage(channel="telegram", chat_id=CHAT, text="third"))
        await settle(runs, gateway)
        chat = (await http.get(f"/api/conversations/{ASSISTANT_ID}")).json()

    assert _prompts(chat) == ["first", "in the browser", "third"]
    assert bot.sent == [(CHAT, "one"), (CHAT, "three")]


async def test_a_telegram_chat_from_before_lands_in_assistants_chat_too(tmp_path) -> None:
    bot, http, gateway, runs = build(tmp_path, "the answer")
    (tmp_path / "chats").mkdir()
    (tmp_path / "chats" / f"telegram-{CHAT}.json").write_text(
        json.dumps(
            {
                "channel": "telegram",
                "chat_id": CHAT,
                "conversation_id": "an-old-chat",
                "delivered_through": 500,
                "pending": [],
            }
        ),
        encoding="utf-8",
    )
    async with http:
        await gateway.receive(InboundMessage(channel="telegram", chat_id=CHAT, text="still here"))
        await settle(runs, gateway)
        chat = (await http.get(f"/api/conversations/{ASSISTANT_ID}")).json()

    assert _prompts(chat) == ["still here"]
    assert bot.sent == [(CHAT, "the answer")]


async def test_a_telegram_message_sent_during_a_browser_turn_is_answered_after_it(tmp_path) -> None:
    release = asyncio.Event()
    bot, http, gateway, runs = build_on(tmp_path, HeldClient(release, "from the web", "to you"))
    async with http:
        sent = await http.post(
            f"/api/conversations/{ASSISTANT_ID}/messages", json={"prompt": "in the browser"}
        )
        assert sent.status_code == 202
        queued = await gateway.receive(
            InboundMessage(channel="telegram", chat_id=CHAT, text="from my phone")
        )
        state = await JsonlChatRepository(tmp_path / "chats").load("telegram", CHAT)
        assert queued is None and state is not None and state.pending == ("from my phone",)
        release.set()
        await settle(runs, gateway)
        chat = (await http.get(f"/api/conversations/{ASSISTANT_ID}")).json()

    assert _prompts(chat) == ["in the browser", "from my phone"]
    assert bot.sent == [(CHAT, "to you")]
