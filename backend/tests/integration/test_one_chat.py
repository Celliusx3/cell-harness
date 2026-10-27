"""A Telegram chat linked to Assistant writes into its one chat, the same one the browser shows."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx

from harness.bots import ASSISTANT_ID, BotService
from harness.channels.gateway import ChannelGateway
from harness.channels.protocol import InboundMessage
from harness.channels.repositories.jsonl import JsonlChatRepository
from harness.llm import LLMClient, Message, StreamEvent, ToolSpec
from harness.runs.bot_messages import BotMessages
from harness.runs.service import RunService
from harness.runtime.service import Runtime
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.web.server import create_app
from tests.unit.fakes import OneModel, SteppedClient, completed
from tests.unit.helpers import client_tools, link_to_assistant, no_approvals, no_skills
from tests.unit.telegram_fakes import telegram_channel
from tests.webapp import channels_of, secrets_in, web_gateway, web_mcp

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
    bots = BotService(tmp_path / "bots.json", sessions, assistant_instructions="ASSISTANT")
    runtime = Runtime(models=OneModel(model), images=None, checkpoint=sessions.flush)
    runs = RunService(sessions, runtime, bots)
    gateway, web = web_gateway(tmp_path, sessions, runs, skills=no_skills())
    channel, bot = telegram_channel(gateway)
    gateway.register(channel)
    app = create_app(
        runs,
        channels_of(gateway, web, secrets_in(tmp_path)),
        web_mcp(),
        no_skills(),
        client_tools(),
        no_approvals(),
        bots,
        secrets_in(tmp_path),
        BotMessages(sessions, bots, runs),
    )
    http = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")
    return bot, http, gateway, runs


async def settle(runs: RunService, gateway: ChannelGateway) -> None:
    for _ in range(300):
        task = gateway._tasks.get(("telegram", CHAT))
        busy = task is not None and not task.done()
        if not busy and not any(runs._runs.values()):
            return
        await asyncio.sleep(0.01)
    raise AssertionError("channel never went idle")


def _prompts(chat: dict) -> list[str]:
    return [e["message"]["content"] for e in chat["events"] if e["type"] == "user/message"]


async def _linked(tmp_path) -> None:
    await link_to_assistant(JsonlChatRepository(tmp_path / "chats"), "telegram", CHAT)


async def test_a_telegram_message_lands_in_assistants_chat(tmp_path) -> None:
    bot, http, gateway, runs = build(tmp_path, "the answer")
    await _linked(tmp_path)
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
    await _linked(tmp_path)
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
    await _linked(tmp_path)
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
