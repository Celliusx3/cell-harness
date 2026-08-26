"""What the gateway reads off a channel, and what it refuses to assume.

Two things vary between platforms and both live on the channel: whether it can be
**sent to** (`Pushing`), and what a **missing conversation** means (`on_missing`).
Everything here is about those two and nothing else.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from harness.agent.loop import LoopAgent
from harness.channels.gateway import ChannelGateway
from harness.channels.repositories.jsonl import JsonlChatRepository
from harness.channels.transport import InboundMessage, Pushing
from harness.channels.web.channel import WebChannel
from harness.runs.store import RunStore
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.repository import SessionNotFoundError
from harness.session.service import SessionService
from tests.unit.fakes import ScriptedClient, completed


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
    gateway = ChannelGateway(chats, runs, sessions)
    web = WebChannel(sessions, runs, gateway)
    gateway.register(web)
    return gateway, web, runs, chats, sessions


async def settle(runs: RunStore, gateway: ChannelGateway, key) -> None:
    for _ in range(300):
        task = gateway._following.get(key)
        busy = task is not None and not task.done()
        if not busy and not any(runs._runs.values()):
            return
        await asyncio.sleep(0.01)
    raise AssertionError("gateway never went idle")


# ── the capability split ──────────────────────────────────────────────────────


def test_a_browser_cannot_be_sent_to() -> None:
    """The claim the whole split rests on.

    `hermes-agent` put `send()` on every platform and had its API server return
    `success=False` forever. Absence is the alternative, and this is the assertion
    that the absence is real rather than a comment.
    """
    assert not isinstance(WebChannel, Pushing)
    assert not hasattr(WebChannel, "send_message")


async def test_a_queued_message_on_a_pull_channel_is_still_answered(tmp_path) -> None:
    """**The drain is not part of delivery, and this is why it cannot be.**

    A pull channel is sent nothing, so it was briefly not followed at all — and
    the queue is drained by the follower. The result was a browser message typed
    mid-turn sitting in `pending` until something else happened to arrive, which
    for a one-off question is never. Delivery varies by channel; the drain does
    not.
    """
    gateway, _, runs, chats, sessions = build(tmp_path)
    session = await sessions.create()
    # Start a turn and queue behind it before it settles.
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
    """ "It will not answer" is a real alarm for a dead poller and a false one here.

    A pull channel's `run()` returning means only that it stopped waiting — its
    receiving is uvicorn's, and it goes on answering. A warning that cries wolf is
    how people learn to ignore the true one.
    """
    gateway, web, _, _, _ = build(tmp_path)
    web.run = _returns_immediately  # type: ignore[method-assign]

    with caplog.at_level(logging.WARNING, logger="harness.channels"):
        await gateway.start()
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    assert "will not answer" not in caplog.text


async def _returns_immediately() -> None:
    return None


# ── on_missing ────────────────────────────────────────────────────────────────


async def test_a_client_channel_refuses_to_invent_a_conversation(tmp_path) -> None:
    """A mistyped id is a mistake to report, not an instruction to create.

    Without this the gateway falls through to "first message in a new chat" and
    quietly makes `c999` real — so a typo in the address bar becomes a
    conversation, and the 404 the browser needs never happens.
    """
    gateway, _, _, _, sessions = build(tmp_path)

    with pytest.raises(SessionNotFoundError):
        await gateway.receive(InboundMessage(channel="web", chat_id="c999", text="hello"))

    assert await sessions.list() == []


async def test_a_client_channel_resolves_a_conversation_it_has_never_seen(tmp_path) -> None:
    """**The browser replying to a Telegram conversation.**

    There is no `("web", <id>)` mapping — that conversation was created by another
    channel — but a browser names the conversation it wants, so the chat id *is*
    the answer. This failed once, with a 404 on a conversation plainly on disk.
    """
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
