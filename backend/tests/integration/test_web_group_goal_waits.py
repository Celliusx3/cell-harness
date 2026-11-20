"""A goal run hears its team's ticket reports inside it, and stops on a busy or looping team."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Mapping, Sequence

import pytest

from harness.llm import LLMClient, Message, StreamEvent, SystemMessage, ToolSpec
from harness.runs.service import goal_wait
from harness.tools.native.tickets import TICKET_REPORT, TICKET_ROUTE
from tests.integration.test_web_group_goal import TASK, _lead, _of_type, _speakers
from tests.integration.test_web_groups import RESEARCHER, WRITER
from tests.integration.ticket_helpers import WORKER_START, Ticketing, ticketing_app
from tests.integration.web_helpers import settle
from tests.unit.fakes import PerBotClient, calls_tool, completed, reports_ready

LEAD = RESEARCHER["instructions"]
MEMBER = WRITER["instructions"]
BUSY = "Writer is still busy with its worker; pick another member or end the run."


def _route(title: str, call_id: str) -> list:
    item = {"kind": "accept", "title": title, "task": f"Do {title}."}
    return calls_tool(TICKET_ROUTE, json.dumps({"items": [item]}), id=call_id)


class _HeldWorkers(LLMClient):
    """`model`, except that a worker's turn never ends."""

    def __init__(self, model: PerBotClient) -> None:
        self._model = model

    async def stream_completion(
        self, messages: list[Message], *, tools: list[ToolSpec] | None = None
    ) -> AsyncIterator[StreamEvent]:
        system = messages[0]
        if isinstance(system, SystemMessage) and system.content.startswith(WORKER_START):
            await asyncio.Event().wait()
        async for event in self._model.stream_completion(messages, tools=tools):
            yield event


async def _team(
    tmp_path, scripts: Mapping[str, Sequence[Sequence[StreamEvent]]], *, held: bool = False
) -> tuple[Ticketing, str, str, str]:
    world = ticketing_app(tmp_path, scripts, around=_HeldWorkers if held else lambda m: m)
    setup = world.client
    researcher = (await setup.post("/api/bots", json=RESEARCHER)).json()["id"]
    writer = (await setup.post("/api/bots", json=WRITER)).json()["id"]
    created = await setup.post(
        "/api/groups", json={"name": "Launch", "member_ids": [researcher, writer]}
    )
    assert created.status_code == 201, created.text
    return world, created.json()["id"], researcher, writer


async def _goal(world: Ticketing, chat: str, prompt: str) -> list[dict]:
    client = world.client
    sent = await client.post(f"/api/conversations/{chat}/messages", json={"prompt": prompt})
    assert sent.status_code == 202, sent.text
    await asyncio.wait_for(_settled(world, chat), timeout=10)
    events = (await client.get(f"/api/conversations/{chat}")).json()["events"]
    await world.tickets.aclose()
    await client.aclose()
    return events


async def _settled(world: Ticketing, chat: str) -> None:
    while world.runs.active_run(chat) is not None:
        await settle(world.runs, chat)


def _after(events: list[dict], first: str, then: str) -> bool:
    kinds = [e["type"] for e in events]
    return kinds.index(first) < kinds.index(then)


async def test_the_lead_speaks_only_after_the_member_heard_its_worker_s_report(tmp_path) -> None:
    world, chat, researcher, writer = await _team(
        tmp_path,
        {
            LEAD: [
                _lead("Writer, over to you.", "continue", next="Writer", task=TASK),
                _lead("We have them.", "done", detail="Risks listed."),
            ],
            MEMBER: [
                _route("Risks", "r1"),
                completed("My worker is on it."),
                completed("Writer: rain, staff, servers."),
            ],
            WORKER_START: [reports_ready("Rain, staff, servers.")],
        },
    )
    events = await _goal(world, chat, "/goal decide whether to launch on Friday")

    assert _speakers(events) == [researcher, writer, writer, researcher]
    starts = [i for i, e in enumerate(events) if e["type"] == "turn/start"]
    [report] = [i for i, e in enumerate(events) if e["type"] == "ticket/report"]
    replies = [i for i, e in enumerate(events) if e["type"] == "assistant/message"]
    heard_reply = next(i for i in replies if "rain, staff" in json.dumps(events[i]))
    assert starts[2] < report < heard_reply < starts[3]
    steps = [(s["role"], s["step"]) for s in _of_type(events, "goal/step")]
    assert steps == [("lead", 1), ("member", 2), ("member", 2), ("lead", 3)]
    [end] = _of_type(events, "goal/end")
    assert (end["status"], end["turns_used"]) == ("done", 3)


async def test_a_member_busy_past_the_limit_is_noted_then_blocks_the_third_time(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(goal_wait, "GOAL_WAIT_SECONDS", 0.05)
    world, chat, *_ = await _team(
        tmp_path,
        {
            LEAD: [
                _lead("Writer, one.", "continue", next="Writer", task="Task one."),
                _lead("Writer, two.", "continue", next="Writer", task="Task two."),
                _lead("Writer, three.", "continue", next="Writer", task="Task three."),
            ],
            MEMBER: [
                _route("One", "r1"),
                completed("Started one."),
                _route("Two", "r2"),
                completed("Started two."),
                _route("Three", "r3"),
                completed("Started three."),
            ],
        },
        held=True,
    )
    events = await _goal(world, chat, "/goal plan the launch")

    notes = [s["note"] for s in _of_type(events, "goal/step") if s["role"] == "lead"]
    assert notes == [None, BUSY, BUSY]
    [end] = _of_type(events, "goal/end")
    assert (end["status"], end["turns_used"]) == ("blocked", 6)
    assert end["detail"] == "Members stayed busy past the wait limit 3 times."


async def test_the_same_task_given_to_the_same_member_a_third_time_blocks(tmp_path) -> None:
    world, chat, *_ = await _team(
        tmp_path,
        {
            LEAD: [
                _lead("Again.", "continue", next="Writer", task=TASK),
                _lead("Again.", "continue", next="Writer", task=f"  {TASK.upper()} "),
                _lead("Again.", "continue", next="writer", task=TASK.replace(" ", "   ")),
            ],
            MEMBER: [completed("Done.")],
        },
    )
    events = await _goal(world, chat, "/goal never finish")

    assert len(_speakers(events)) == 5
    [end] = _of_type(events, "goal/end")
    assert (end["status"], end["turns_used"]) == ("blocked", 5)
    assert end["detail"] == "The team repeated the same assignment three times without finishing."


async def test_a_worker_s_question_for_the_person_ends_the_run_needing_you(tmp_path) -> None:
    question = "Direct or 1-stop?"
    world, chat, *_ = await _team(
        tmp_path,
        {
            LEAD: [_lead("Writer, book it.", "continue", next="Writer", task=TASK)],
            MEMBER: [
                _route("Flight", "r1"),
                completed("Booking."),
                completed("The worker asks: direct or 1-stop?"),
            ],
            WORKER_START: [
                calls_tool(
                    TICKET_REPORT,
                    json.dumps({"state": "blocked", "summary": "Two kinds.", "question": question}),
                    id="w1",
                )
            ],
        },
    )
    events = await _goal(world, chat, "/goal book a flight")

    [end] = _of_type(events, "goal/end")
    assert (end["status"], end["detail"], end["turns_used"]) == ("needs_you", question, 2)
    assert _after(events, "ticket/report", "goal/end")
