"""A gateway with one Telegram bot on it, for the gateway tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

from harness.channels.gateway import ChannelGateway
from harness.channels.protocol import InboundMessage
from harness.channels.repositories.jsonl import JsonlChatRepository
from harness.runs.store import RunStore
from harness.skills import SkillService
from tests.unit.helpers import durable_service, run_store
from tests.unit.telegram_fakes import telegram_channel

CHAT = "4242"


def build(
    tmp_path: Path,
    model,
    *tools,
    public_url: str = "http://t",
    skills: SkillService,
):
    sessions = durable_service(tmp_path / "sessions")
    runs = run_store(sessions, model, *tools)
    chats = JsonlChatRepository(tmp_path / "chats")
    gateway = ChannelGateway(chats, runs, sessions, skills, public_url=public_url)
    channel, bot = telegram_channel(gateway)
    gateway.register(channel)
    return bot, gateway, runs, chats, sessions


def msg(text: str, _seq: int = 0) -> InboundMessage:
    """One inbound message. `_seq` is ignored — kept so the call sites still read
    as a sequence of arrivals now that messages carry no id."""
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
