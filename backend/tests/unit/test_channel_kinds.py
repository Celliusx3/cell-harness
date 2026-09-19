"""What the gateway reads off a channel, and what it refuses to assume."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from harness.agent.loop import LoopAgent
from harness.channels.gateway import ChannelGateway
from harness.channels.protocol import InboundMessage, Pushing
from harness.channels.repositories.jsonl import JsonlChatRepository
from harness.channels.web.channel import WebChannel
from harness.runs.store import RunStore
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.repository import SessionNotFoundError
from harness.session.service import SessionService
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import no_skills


def build(tmp_path: Path):
    ids = iter(f"c{n}" for n in range(100))
    sessions = SessionService(
        JsonlSessionRepository(tmp_path / "sessions"),
        now=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        new_id=lambda: next(ids),
    )
    agent = LoopAgent(
        name="t",
        model="m",
        client=ScriptedClient(completed("answered")),
        checkpoint=sessions.flush,
    )
    runs = RunStore(sessions, agent)
    chats = JsonlChatRepository(tmp_path / "chats")
    gateway = ChannelGateway(chats, runs, sessions, no_skills(), public_url="http://t")
    web = WebChannel(sessions, runs, gateway)
    gateway.register(web)
    return gateway, web, runs, chats, sessions


async def settle(runs: RunStore, gateway: ChannelGateway, key) -> None:
    for _ in range(300):
        task = gateway._tasks.get(key)
        busy = task is not None and not task.done()
        if not busy and not any(runs._runs.values()):
            return
        await asyncio.sleep(0.01)
    raise AssertionError("gateway never went idle")


def test_a_browser_cannot_be_sent_to() -> None:
    assert not isinstance(WebChannel, Pushing)
    assert not hasattr(WebChannel, "send_message")


async def test_a_queued_message_on_a_pull_channel_is_still_answered(tmp_path) -> None:
    gateway, _, runs, chats, sessions = build(tmp_path)
    session = await sessions.create()
    await gateway.start_turn(session, "first", channel="web")
    queued = await gateway.receive(InboundMessage(channel="web", chat_id=session.id, text="second"))

    assert queued is None, "the second message should have been held, not started"
    await settle(runs, gateway, ("web", session.id))

    stored = await sessions.read(session.id)
    prompts = [e.message.content for e in stored.events() if e.type == "user/message"]
    assert prompts == ["first", "second"]
    assert (await chats.load("web", session.id)).pending == ()


async def test_a_pull_channel_that_stops_waiting_is_not_reported_as_broken(
    tmp_path, caplog
) -> None:
    gateway, web, _, _, _ = build(tmp_path)
    web.run = _returns_immediately

    with caplog.at_level(logging.WARNING, logger="harness.channels"):
        await gateway.start()
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    assert "will not answer" not in caplog.text


async def _returns_immediately() -> None:
    return None


async def test_a_client_channel_refuses_to_invent_a_conversation(tmp_path) -> None:
    gateway, _, _, _, sessions = build(tmp_path)

    with pytest.raises(SessionNotFoundError):
        await gateway.receive(InboundMessage(channel="web", chat_id="c999", text="hello"))

    assert await sessions.list() == []


async def test_a_client_channel_resolves_a_conversation_it_has_never_seen(tmp_path) -> None:
    gateway, _, runs, _, sessions = build(tmp_path)
    session = await sessions.create()
    await gateway.start_turn(session, "started elsewhere", channel="web")
    await settle(runs, gateway, ("web", session.id))

    run = await gateway.receive(InboundMessage(channel="web", chat_id=session.id, text="and again"))

    assert run is not None
    await settle(runs, gateway, ("web", session.id))
    stored = await sessions.read(session.id)
    prompts = [e.message.content for e in stored.events() if e.type == "user/message"]
    assert prompts == ["started elsewhere", "and again"]
