"""Runs: a turn that outlives the connection that asked for it."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest

from harness.bots import (
    ASSISTANT_ID,
    Bot,
    BotService,
    ChatMembers,
    GroupDraft,
    GroupEmpty,
)
from harness.prompts import ASSISTANT_INSTRUCTIONS
from harness.runs.service import RunAlreadyActive
from harness.runs.subscribe import subscribe
from harness.session.log import Session
from harness.session.models import (
    ToolCallEvent,
    ToolResultEvent,
    TurnEnd,
    TurnStart,
)
from harness.session.service import SessionService
from harness.tools.context import ToolContext
from harness.tools.definition import Ok, ToolOutcome
from tests.unit.fakes import (
    EchoArgs,
    ScriptedClient,
    SteppedClient,
    calls_tool,
    completed,
    echo_tool,
    hanging_tool,
    pending_tool,
)
from tests.unit.helpers import drain, durable_service, run_service, until
from tests.webapp import bots_in


@pytest.fixture
def service(tmp_path) -> SessionService:
    return durable_service(tmp_path / "sessions")


async def test_a_subscriber_walking_away_does_not_end_the_run(service) -> None:
    runs = run_service(
        service,
        SteppedClient(calls_tool("echo", '{"value": "hi"}'), completed("done")),
        echo_tool(),
    )
    session = await service.create(ASSISTANT_ID)
    run = runs.start(session, "go")

    stream = subscribe(run, after=0)
    await anext(stream)
    await stream.aclose()

    await asyncio.wait_for(run._outer, timeout=5)
    assert run.settled
    assert [e.reason for e in run.session.events() if isinstance(e, TurnEnd)] == ["completed"]


async def test_a_reconnecting_subscriber_misses_nothing(service) -> None:
    runs = run_service(
        service,
        SteppedClient(calls_tool("echo", '{"value": "hi"}'), completed("done")),
        echo_tool(),
    )
    session = await service.create(ASSISTANT_ID)
    run = runs.start(session, "go")

    first = subscribe(run, after=0)
    early = [await anext(first), await anext(first)]
    await first.aclose()

    rest = await drain(subscribe(run, after=early[-1].number + 1))

    seen = [*early, *rest]
    assert seen == list(enumerate(run.session.events()))
    events = [item.event for item in seen]
    assert [e.reason for e in events if isinstance(e, TurnEnd)] == ["completed"]
    assert any(isinstance(e, ToolResultEvent) for e in events)


async def test_subscribing_after_the_turn_ends_replays_everything(service) -> None:
    runs = run_service(service, ScriptedClient(completed("hello")))
    session = await service.create(ASSISTANT_ID)
    run = runs.start(session, "go")
    await asyncio.wait_for(run._outer, timeout=5)

    assert await drain(subscribe(run, after=0)) == list(enumerate(run.session.events()))


async def test_a_settled_run_still_yields_its_last_events(service) -> None:
    runs = run_service(service, ScriptedClient(completed("hello")))
    session = await service.create(ASSISTANT_ID)
    run = runs.start(session, "go")
    await asyncio.wait_for(run._outer, timeout=5)

    last = len(run.session.events()) - 1
    items = await drain(subscribe(run, after=last))

    assert [(item.number, type(item.event)) for item in items] == [(last, TurnEnd)]


async def test_a_subscriber_waiting_when_the_run_settles_is_released(service) -> None:
    runs = run_service(service, ScriptedClient(completed("hello")))
    session = await service.create(ASSISTANT_ID)
    run = runs.start(session, "go")

    collected = await asyncio.wait_for(drain(subscribe(run, after=0)), timeout=5)

    assert collected == list(enumerate(run.session.events()))
    assert run.settled


async def test_a_second_run_on_one_conversation_is_refused(service) -> None:
    runs = run_service(service, ScriptedClient(completed("hello")))
    session = await service.create(ASSISTANT_ID)
    runs.start(session, "first")

    with pytest.raises(RunAlreadyActive):
        runs.start(session, "second")


async def test_a_conversation_is_free_again_once_its_turn_settles(service) -> None:
    runs = run_service(service, ScriptedClient(completed("hello")))
    session = await service.create(ASSISTANT_ID)
    run = runs.start(session, "first")
    await asyncio.wait_for(run._outer, timeout=5)

    assert runs.active(session.id) is None
    runs.start(session, "second")


async def test_starting_is_atomic_against_a_concurrent_start(service) -> None:
    runs = run_service(service, ScriptedClient(completed("hello")))
    session = await service.create(ASSISTANT_ID)

    async def attempt() -> str:
        try:
            runs.start(session, "go")
            return "started"
        except RunAlreadyActive:
            return "refused"

    outcomes = await asyncio.gather(attempt(), attempt(), attempt())

    assert sorted(outcomes) == ["refused", "refused", "started"]


async def test_resume_runs_a_turn_that_starts_with_the_answer(service) -> None:
    client = SteppedClient(calls_tool("ask", '{"value": "?"}', id="c1"), completed("cafés"))
    runs = run_service(service, client, pending_tool())
    session = await service.create(ASSISTANT_ID)
    first = runs.start(session, "near me?")
    await asyncio.wait_for(first._outer, timeout=5)

    assert runs.active(session.id) is None
    run = runs.resume(session, "c1", Ok(content='{"lat": 3.1}'))
    assert runs.active(session.id) is run
    with pytest.raises(RunAlreadyActive):
        runs.resume(session, "c1", Ok(content="again"))
    await asyncio.wait_for(run._outer, timeout=5)

    assert runs.active(session.id) is None
    stored = await service.read(session.id)
    assert [e.reason for e in stored.events() if e.type == "turn/end"] == ["pending", "completed"]


class _ChatsOfNotion(BotService):
    def members_of_chat(self, chat_id: str) -> ChatMembers:
        return ChatMembers(
            group=None, bots=(Bot(id="notion", name="Notion", instructions="Read Notion."),)
        )


async def test_a_turn_runs_its_tools_for_the_bot_that_owns_the_chat(service) -> None:
    seen: list[str] = []

    async def execute(args: EchoArgs, context: ToolContext) -> ToolOutcome:
        seen.append(context.bot_id)
        return Ok(content=args.value)

    bots = _ChatsOfNotion(
        Path("/nonexistent/bots.json"), service, assistant_instructions=ASSISTANT_INSTRUCTIONS
    )
    client = SteppedClient(calls_tool("echo", '{"value": "hi"}'), completed("done"))
    runs = run_service(service, client, replace(echo_tool(), execute=execute), bots=bots)
    run = runs.start(await service.create(ASSISTANT_ID), "go")
    await asyncio.wait_for(run._outer, timeout=5)

    assert seen == ["notion"]


async def _group_chat(
    bots: BotService, service: SessionService, *names: str
) -> tuple[Session, tuple[Bot, ...]]:
    """A group of new bots called `names`, and its chat."""
    members = tuple([await bots.create(name, f"You are {name}.") for name in names])
    group = await bots.create_group(
        GroupDraft(name="Launch", member_ids=tuple(bot.id for bot in members))
    )
    return await service.resume(group.id), members


def _speakers(session: Session) -> list[str | None]:
    return [e.bot_id for e in session.events() if isinstance(e, TurnStart)]


async def test_the_line_carries_on_once_the_person_answers_the_bot_that_asked(
    tmp_path, service
) -> None:
    bots = bots_in(tmp_path, service)
    chat, (researcher, writer) = await _group_chat(bots, service, "Researcher", "Writer")
    client = SteppedClient(
        calls_tool("ask", '{"value": "?"}', id="c1"), completed("Got it."), completed("Draft.")
    )
    runs = run_service(service, client, pending_tool(), bots=bots)
    await asyncio.wait_for(runs.start(chat, "go")._outer, timeout=5)

    assert _speakers(chat) == [researcher.id]
    await asyncio.wait_for(runs.resume(chat, "c1", Ok(content="2024"))._outer, timeout=5)

    assert _speakers(chat) == [researcher.id, researcher.id, writer.id]
    assert [e.reason for e in chat.events() if isinstance(e, TurnEnd)] == [
        "pending",
        "completed",
        "completed",
    ]


async def test_stopping_a_group_ends_the_round_in_one_settled_run(tmp_path, service) -> None:
    bots = bots_in(tmp_path, service)
    chat, (researcher, writer, _) = await _group_chat(bots, service, "Researcher", "Writer", "Ed")
    client = SteppedClient(completed("Sources."), calls_tool("hang", '{"value": "x"}'))
    runs = run_service(service, client, hanging_tool(), bots=bots)
    run = runs.start(chat, "go")
    await until(
        lambda: any(isinstance(e, ToolCallEvent) for e in chat.events()),
        what="the second speaker's call",
    )

    assert await runs.stop(chat.id) is True

    assert run.settled and runs.active(chat.id) is None
    assert _speakers(chat) == [researcher.id, writer.id]
    assert [e.reason for e in chat.events() if isinstance(e, TurnEnd)] == [
        "completed",
        "cancelled",
    ]


async def test_a_group_with_no_active_member_starts_nothing(tmp_path, service) -> None:
    bots = bots_in(tmp_path, service)
    chat, members = await _group_chat(bots, service, "Researcher", "Writer")
    for bot in members:
        bots.archive(bot.id)
    runs = run_service(service, ScriptedClient(completed("x")), bots=bots)

    with pytest.raises(GroupEmpty):
        runs.start(chat, "anyone?")
    assert runs.active(chat.id) is None
