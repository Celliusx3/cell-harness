"""A platform that leaves the gateway takes nothing with it: no raise, and one log line."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import pytest

from harness.bots import ASSISTANT_ID
from harness.channels.gateway import ChannelGateway
from harness.channels.protocol import InboundMessage, TokenRefused
from harness.channels.repositories.jsonl import JsonlChatRepository
from harness.llm import LLMClient
from harness.tools import Tool
from harness.tools.client import PendingCall
from tests.unit.fakes import ScriptedClient, SteppedClient, calls_tool, completed, gated_tool
from tests.unit.helpers import durable_service, no_skills, run_service, until

LEFT = "has left"


class PullingChannel:
    """A platform the gateway never sends to."""

    channel = "telegram"

    def conversation_for(self, chat_id: str) -> str:
        return ASSISTANT_ID

    async def run(self) -> None:
        await asyncio.Event().wait()


class PushingChannel(PullingChannel):
    """A platform that records each reply sent to it."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_message(self, chat_id: str, text: str) -> None:
        self.sent.append(text)

    async def send_typing(self, chat_id: str) -> None:
        return None

    async def send_link(self, chat_id: str, text: str, url: str) -> None:
        self.sent.append(url)

    async def ask_client(self, chat_id: str, request: PendingCall, url: str) -> None:
        self.sent.append(url)


class RefusedChannel(PullingChannel):
    """A platform that refuses its token the moment it starts."""

    async def run(self) -> None:
        raise TokenRefused("Telegram refused the bot token")


def _gateway(tmp_path: Path, model: LLMClient, *tools: Tool) -> ChannelGateway:
    sessions = durable_service(tmp_path / "sessions")
    runs = run_service(sessions, model, *tools)
    chats = JsonlChatRepository(tmp_path / "chats")
    return ChannelGateway(chats, runs, sessions, no_skills(), public_url="http://t")


def _message(text: str) -> InboundMessage:
    return InboundMessage(channel="telegram", chat_id="1", text=text)


def _left_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [record.getMessage() for record in caplog.records if LEFT in record.getMessage()]


async def _settled(gateway: ChannelGateway) -> None:
    await until(lambda: not gateway._tasks.running() and not gateway.runs._runs, what="idle")


async def test_a_channel_that_stopped_on_its_own_is_disposed_of_without_raising(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    gateway = _gateway(tmp_path, ScriptedClient(completed("hi")))
    await gateway.start()
    dispose = gateway.register(RefusedChannel())
    await until(lambda: "telegram channel stopped" in caplog.text, what="the refusal")

    await dispose()

    assert gateway.channels == []
    await gateway.aclose()


async def test_a_reply_for_a_platform_that_left_is_dropped_with_one_log_line(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="harness.channels")
    gateway = _gateway(tmp_path, ScriptedClient(completed("hi")))
    await gateway.start()
    channel = PushingChannel()
    dispose = gateway.register(channel)

    run = await gateway.receive(_message("hello"))
    await dispose()
    await _settled(gateway)

    assert run is not None and run.error is None
    assert channel.sent == []
    assert len(_left_lines(caplog)) == 1
    await gateway.aclose()


async def test_a_follow_on_for_a_platform_that_left_is_dropped_with_one_log_line(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="harness.channels")
    release = asyncio.Event()
    model = SteppedClient(calls_tool("gate", '{"value": "x"}'), completed("done"))
    gateway = _gateway(tmp_path, model, gated_tool(release))
    await gateway.start()
    dispose = gateway.register(PullingChannel())
    first = await gateway.receive(_message("one"))
    queued = await gateway.receive(_message("two"))
    await asyncio.sleep(0)

    await dispose()
    release.set()
    await _settled(gateway)

    assert first is not None and first.error is None
    assert queued is None
    assert model.calls == 2
    assert len(_left_lines(caplog)) == 1
    await gateway.aclose()
