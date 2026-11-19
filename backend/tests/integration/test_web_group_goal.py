"""`/goal` in a group over HTTP: the lead and the member it names take turns until it ends."""

from __future__ import annotations

import asyncio
import json

from harness.llm import StreamFailure, SystemMessage
from tests.integration.test_web_groups import _group, _send
from tests.unit.fakes import calls_tool, completed, hanging_tool

TASK = "List three risks of launching on Friday."


def _decision(status: str, **fields: str) -> str:
    return f"<goal>{json.dumps({'status': status, **fields})}</goal>"


def _lead(text: str, status: str, **fields: str) -> list:
    return completed(f"{text}\n{_decision(status, **fields)}")


def _speakers(events: list[dict]) -> list[str]:
    return [e["bot_id"] for e in events if e["type"] == "turn/start"]


def _of_type(events: list[dict], kind: str) -> list[dict]:
    return [e for e in events if e["type"] == kind]


async def test_the_lead_hands_a_task_to_a_member_then_ends_the_run_done(tmp_path) -> None:
    client, model, runs, chat, researcher, writer = await _group(
        tmp_path,
        _lead("Writer, over to you.", "continue", next="Writer", task=TASK),
        completed("Researcher: rain, staff, servers."),
        _lead("We have the three risks.", "done", detail="Risks listed."),
    )
    async with client:
        events = await _send(client, runs, chat, "/goal decide whether to launch on Friday")

    assert _speakers(events) == [researcher, writer, researcher]
    [start] = _of_type(events, "goal/start")
    assert (start["goal"], start["lead_id"], start["max_turns"]) == (
        "decide whether to launch on Friday",
        researcher,
        13,
    )
    steps = [(s["bot_id"], s["role"], s["step"], s["task"]) for s in _of_type(events, "goal/step")]
    assert steps == [
        (researcher, "lead", 1, None),
        (writer, "member", 2, TASK),
        (researcher, "lead", 3, None),
    ]
    [end] = _of_type(events, "goal/end")
    assert (end["status"], end["detail"], end["turns_used"]) == ("done", "Risks listed.", 3)
    messages = [e["message"]["content"] for e in _of_type(events, "user/message")]
    assert messages == ["/goal decide whether to launch on Friday"]
    member_system = model.seen_per_call[1][0]
    assert isinstance(member_system, SystemMessage)
    assert TASK in member_system.content
    assert "Researcher" in member_system.content
    lead_system = model.seen_per_call[0][0]
    assert isinstance(lead_system, SystemMessage)
    assert "12 turn(s) remain" in lead_system.content


async def test_a_lead_reply_with_no_block_ends_the_run_blocked(tmp_path) -> None:
    client, _, runs, chat, researcher, _ = await _group(tmp_path, completed("I will think."))
    async with client:
        events = await _send(client, runs, chat, "/goal plan the launch")

    assert _speakers(events) == [researcher]
    [end] = _of_type(events, "goal/end")
    assert (end["status"], end["turns_used"]) == ("blocked", 1)
    assert end["detail"] == "Researcher did not give a valid next step."


async def test_a_lead_that_always_continues_stops_at_the_turn_limit(tmp_path) -> None:
    client, model, runs, chat, researcher, writer = await _group(
        tmp_path, _lead("Again.", "continue", next="writer", task=TASK)
    )
    async with client:
        events = await _send(client, runs, chat, "/goal never finish")

    assert _speakers(events) == [researcher, writer] * 6 + [researcher]
    [end] = _of_type(events, "goal/end")
    assert (end["status"], end["turns_used"]) == ("limit_reached", 13)
    last_lead = model.seen_per_call[12][0]
    assert isinstance(last_lead, SystemMessage)
    assert "last turn" in last_lead.content


async def test_a_member_named_in_the_goal_leads_it(tmp_path) -> None:
    client, _, runs, chat, researcher, writer = await _group(
        tmp_path,
        _lead("Researcher, your turn.", "continue", next="Researcher", task=TASK),
        completed("Done."),
        _lead("All set.", "done", detail="Done."),
    )
    async with client:
        events = await _send(client, runs, chat, "/goal @Writer write the launch post")

    [start] = _of_type(events, "goal/start")
    assert start["lead_id"] == writer
    assert _speakers(events) == [writer, researcher, writer]


async def test_a_mention_in_a_reply_brings_nobody_into_a_goal_run(tmp_path) -> None:
    client, model, runs, chat, researcher, writer = await _group(
        tmp_path,
        _lead("@Writer please.", "continue", next="Writer", task=TASK),
        completed("Here. @Researcher @Writer have a look."),
        _lead("Thanks.", "done", detail="Done."),
    )
    async with client:
        events = await _send(client, runs, chat, "/goal draft the post")

    assert _speakers(events) == [researcher, writer, researcher]
    assert model.calls == 3


async def test_a_lead_naming_nobody_in_the_group_ends_the_run_blocked(tmp_path) -> None:
    client, _, runs, chat, researcher, _ = await _group(
        tmp_path, _lead("Over to Ghost.", "continue", next="Ghost", task=TASK)
    )
    async with client:
        events = await _send(client, runs, chat, "/goal plan")

    assert _speakers(events) == [researcher]
    [end] = _of_type(events, "goal/end")
    assert (end["status"], end["turns_used"]) == ("blocked", 1)


async def test_a_lead_that_needs_the_person_ends_the_run_saying_so(tmp_path) -> None:
    client, _, runs, chat, _, _ = await _group(
        tmp_path, _lead("Which day?", "needs_you", detail="Pick a launch day.")
    )
    async with client:
        events = await _send(client, runs, chat, "/goal plan")

    [end] = _of_type(events, "goal/end")
    assert (end["status"], end["detail"]) == ("needs_you", "Pick a launch day.")


async def test_goal_in_a_bot_s_own_chat_is_still_an_unknown_skill(tmp_path) -> None:
    client, _, _, _, researcher, _ = await _group(tmp_path, completed("Hi."))
    async with client:
        sent = await client.post(
            f"/api/conversations/{researcher}/messages", json={"prompt": "/goal plan"}
        )

    assert sent.status_code == 422, sent.text


async def test_a_member_turn_that_fails_ends_the_run_failed(tmp_path) -> None:
    client, _, runs, chat, _, _ = await _group(
        tmp_path,
        _lead("Writer, go.", "continue", next="Writer", task=TASK),
        [StreamFailure(reason="the model is down")],
    )
    async with client:
        events = await _send(client, runs, chat, "/goal plan")

    [end] = _of_type(events, "goal/end")
    assert (end["status"], end["turns_used"]) == ("failed", 2)
    assert end["detail"] == "Writer could not return a result to Researcher."


async def test_a_lead_turn_that_fails_ends_the_run_failed(tmp_path) -> None:
    client, _, runs, chat, _, _ = await _group(tmp_path, [StreamFailure(reason="down")])
    async with client:
        events = await _send(client, runs, chat, "/goal plan")

    [end] = _of_type(events, "goal/end")
    assert (end["status"], end["detail"]) == ("failed", "Researcher could not finish its turn.")


async def test_a_stopped_goal_run_logs_no_ending_of_its_own(tmp_path) -> None:
    client, _, runs, chat, _, writer = await _group(
        tmp_path,
        _lead("Writer, go.", "continue", next="Writer", task=TASK),
        calls_tool("hang", '{"value": "x"}'),
        extra=(hanging_tool(),),
    )
    async with client:
        sent = await client.post(f"/api/conversations/{chat}/messages", json={"prompt": "/goal x"})
        assert sent.status_code == 202
        for _ in range(200):
            running = runs.active_run(chat)
            if running is not None and running.session.speaker_id() == writer:
                break
            await asyncio.sleep(0.01)
        stopped = await client.delete(f"/api/conversations/{chat}/run")
        events = (await client.get(f"/api/conversations/{chat}")).json()["events"]

    assert stopped.status_code == 204
    assert _of_type(events, "goal/end") == []
    assert runs.active_run(chat) is None
