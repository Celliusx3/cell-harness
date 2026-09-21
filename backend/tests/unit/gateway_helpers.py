"""A gateway with one Telegram bot on it, for the gateway tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

from harness.channels.client import ChatAnswers
from harness.channels.gateway import ChannelGateway
from harness.channels.protocol import InboundMessage
from harness.channels.repositories.jsonl import JsonlChatRepository
from harness.runs.store import RunStore
from harness.skills import SkillService
from harness.tools.approval import ApprovalGate
from harness.tools.client import ClientToolService
from tests.unit.helpers import client_tools as default_client_tools
from tests.unit.helpers import durable_service, run_store
from tests.unit.telegram_fakes import telegram_channel

CHAT = "4242"


def build(
    tmp_path: Path,
    model,
    *tools,
    public_url: str = "http://t",
    skills: SkillService,
    client_tools: ClientToolService | None = None,
    compaction=None,
    gate: ApprovalGate | None = None,
):
    sessions = durable_service(tmp_path / "sessions")
    runs = run_store(sessions, model, *tools, compaction=compaction, gate=gate)
    chats = JsonlChatRepository(tmp_path / "chats")
    client_tools = client_tools or default_client_tools()
    gateway = ChannelGateway(
        chats, runs, sessions, skills, public_url=public_url, client_tools=client_tools.awaited
    )
    channel, bot = telegram_channel(gateway, ChatAnswers(chats, sessions, gateway, client_tools))
    gateway.register(channel)
    return bot, gateway, runs, chats, sessions


def msg(text: str, _seq: int = 0) -> InboundMessage:
    """One inbound message."""
    return InboundMessage(channel="telegram", chat_id=CHAT, text=text)


async def settle(runs: RunStore, gateway: ChannelGateway, chat_id: int = CHAT) -> None:
    """Let the turn, its delivery, and any drained follow-on finish."""
    for _ in range(200):
        task = gateway._tasks.get(("telegram", chat_id))
        busy = task is not None and not task.done()
        if not busy and not any(runs._runs.values()):
            return
        await asyncio.sleep(0.01)
    raise AssertionError("channel never went idle")
