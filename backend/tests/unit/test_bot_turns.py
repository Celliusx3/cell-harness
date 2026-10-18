"""A bot's turns are prompted with its own logged instructions, and in a group, what others said."""

from __future__ import annotations

import asyncio
from pathlib import Path

from harness.bots import ASSISTANT_ID, BotDraft, BotService
from harness.llm import (
    ApplicationMessage,
    AssistantMessage,
    SystemMessage,
    Text,
    ToolCall,
    ToolMessage,
    ToolReference,
    UserMessage,
)
from harness.runs.service import RunService
from harness.session.compaction import CompactionEnd
from harness.session.log import Session
from harness.session.models import (
    ApplicationMessageEvent,
    ApprovalGrant,
    AssistantMessageEvent,
    BotInstructionsEvent,
    GroupMembersEvent,
    SessionEvent,
    ToolCallEvent,
    ToolResultEvent,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)
from harness.tools.definition import Ok
from tests.unit.fakes import ScriptedClient, SteppedClient, calls_tool, completed, pending_tool
from tests.unit.helpers import durable_service, new_session, runtime_over


def _logged(session: Session) -> list[str]:
    return [e.instructions for e in session.events() if isinstance(e, BotInstructionsEvent)]


def test_the_last_instructions_logged_prompt_the_turn_even_behind_a_compaction() -> None:
    session = new_session()
    session.append(BotInstructionsEvent(name="Researcher", instructions="Find sources."))
    session.append(BotInstructionsEvent(name="Researcher", instructions="Cite."))
    session.append(TurnStart(turn=0))
    session.append(UserMessageEvent(turn=0, message=UserMessage(content="q")))
    session.append(CompactionEnd(turn=0, message=ApplicationMessage(content="SUMMARY")))

    messages = runtime_over(ScriptedClient([]), guidance="GUIDE").request_messages(session)

    assert messages == [SystemMessage(content="Cite. GUIDE"), UserMessage(content="SUMMARY")]


def test_an_agent_with_no_prompt_of_its_own_sends_the_instructions_alone() -> None:
    session = new_session()
    session.append(BotInstructionsEvent(name="Researcher", instructions="Cite."))

    system = runtime_over(ScriptedClient([])).request_messages(session)[0]

    assert system == SystemMessage(content="Cite.")


async def test_a_compaction_is_prompted_as_the_turns_were_and_logs_no_edit(
    tmp_path: Path,
) -> None:
    service = durable_service(tmp_path / "sessions")
    bots = BotService(tmp_path / "bots.json", service, assistant_instructions="Be kind.")
    client = ScriptedClient(completed("THE SUMMARY"))
    runtime = runtime_over(client, guidance="GUIDE", checkpoint=service.flush, context_tokens=None)
    runs = RunService(service, runtime, bots)
    session = await service.create(ASSISTANT_ID)
    await asyncio.wait_for(runs.start(session, "hi")._outer, timeout=5)
    bots.update(ASSISTANT_ID, BotDraft(name="Assistant", instructions="Be brief."))

    await asyncio.wait_for(runs.compact(session)._outer, timeout=5)

    assert client.seen[0] == SystemMessage(content="Be kind. GUIDE")
    assert _logged(session) == ["Be kind."]


async def test_an_answer_resumes_the_turn_without_logging_an_edit(tmp_path: Path) -> None:
    service = durable_service(tmp_path / "sessions")
    bots = BotService(tmp_path / "bots.json", service, assistant_instructions="Be kind.")
    client = SteppedClient(calls_tool("ask", '{"value": "?"}', id="c1"), completed("cafés"))
    runs = RunService(service, runtime_over(client, pending_tool(), checkpoint=service.flush), bots)
    session = await service.create(ASSISTANT_ID)
    await asyncio.wait_for(runs.start(session, "near me?")._outer, timeout=5)
    bots.update(ASSISTANT_ID, BotDraft(name="Assistant", instructions="Be brief."))

    await asyncio.wait_for(runs.resume(session, "c1", Ok(content="here"))._outer, timeout=5)

    assert client.seen[0] == SystemMessage(content="Be kind.")
    assert _logged(session) == ["Be kind."]


async def test_a_chat_from_before_groups_logs_its_bot_s_instructions_no_second_time(
    tmp_path: Path,
) -> None:
    service = durable_service(tmp_path / "sessions")
    bots = BotService(tmp_path / "bots.json", service, assistant_instructions="Be kind.")
    runs = RunService(service, runtime_over(ScriptedClient(completed("Hi."))), bots)
    session = await service.create(ASSISTANT_ID)
    session.append(BotInstructionsEvent(name="Assistant", instructions="Be kind."))

    await asyncio.wait_for(runs.start(session, "hi")._outer, timeout=5)

    assert _logged(session) == ["Be kind."]
    assert [e.bot_id for e in session.events() if isinstance(e, TurnStart)] == [ASSISTANT_ID]


CALL = ToolCall(id="c1", name="web__get", arguments="{}")


def log_of(*events: SessionEvent) -> Session:
    session = new_session()
    for event in events:
        session.append(event)
    return session


def instructions(bot_id: str, name: str) -> BotInstructionsEvent:
    return BotInstructionsEvent(name=name, instructions=f"You are {name}.", bot_id=bot_id)


def said(turn: int, text: str, *calls: ToolCall) -> AssistantMessageEvent:
    return AssistantMessageEvent(
        turn=turn, step=0, message=AssistantMessage(content=text, tool_calls=calls)
    )


def selected(turn: int, call_id: str, tool: str) -> ToolResultEvent:
    blocks = (Text(text="ok"), ToolReference(tool_name=tool))
    return ToolResultEvent(
        turn=turn, step=0, message=ToolMessage(tool_call_id=call_id, content=blocks)
    )


RESEARCHER_TURN = (
    instructions("r", "Researcher"),
    TurnStart(turn=0, bot_id="r"),
    UserMessageEvent(turn=0, message=UserMessage(content="what now?")),
    said(0, "Checking.", CALL),
    ToolCallEvent(turn=0, step=0, call=CALL),
    selected(0, "c1", "web__get"),
    ApplicationMessageEvent(turn=0, message=ApplicationMessage(content="a reminder")),
    said(0, "Three trends."),
    TurnEnd(turn=0, reason="completed"),
)


def test_another_bot_s_turn_is_one_tagged_message_of_what_it_said() -> None:
    session = log_of(*RESEARCHER_TURN, instructions("w", "Writer"), TurnStart(turn=1, bot_id="w"))

    messages = runtime_over(ScriptedClient([])).request_messages(session)

    assert messages[1:] == [
        UserMessage(content="what now?"),
        UserMessage(content='<speaker name="Researcher" />\nChecking.\n\nThree trends.'),
    ]


def test_a_reply_of_no_response_or_nothing_is_not_shown_to_the_others() -> None:
    session = log_of(
        instructions("r", "Researcher"),
        TurnStart(turn=0, bot_id="r"),
        UserMessageEvent(turn=0, message=UserMessage(content="hi")),
        said(0, "  NO_RESPONSE\n"),
        said(0, " "),
        TurnEnd(turn=0, reason="completed"),
        TurnStart(turn=1, bot_id="w"),
    )

    assert runtime_over(ScriptedClient([])).request_messages(session) == [UserMessage(content="hi")]


def test_a_turn_cut_by_a_compaction_is_still_told_apart_by_its_speaker() -> None:
    session = log_of(
        instructions("r", "Researcher"),
        TurnStart(turn=0, bot_id="r"),
        UserMessageEvent(turn=0, message=UserMessage(content="hi")),
        CompactionEnd(turn=0, message=ApplicationMessage(content="SUMMARY")),
        said(0, "Three trends."),
        TurnEnd(turn=0, reason="completed"),
        TurnStart(turn=1, bot_id="w"),
    )

    assert runtime_over(ScriptedClient([])).request_messages(session) == [
        UserMessage(content="SUMMARY"),
        UserMessage(content='<speaker name="Researcher" />\nThree trends.'),
    ]


def test_a_bot_is_told_its_group_and_the_others_in_it_by_name() -> None:
    session = log_of(
        GroupMembersEvent(name="Launch", members=("Researcher", "Writer", "Editor", "Critic")),
        instructions("w", "Writer"),
        TurnStart(turn=0, bot_id="w"),
    )

    system = runtime_over(ScriptedClient([]), guidance="GUIDE").request_messages(session)[0]

    note = (
        'You are Writer, one of the bots in the group chat "Launch", talking with the person '
        "and Researcher, Editor and Critic. A message from another bot starts with a speaker "
        "tag naming who wrote it; the person's messages have no tag. To ask another bot in "
        "this group to respond, write @ followed by its name. When a message is not addressed "
        "to you and you have nothing useful to add, reply with exactly NO_RESPONSE and nothing "
        "else; it is not shown to anyone."
    )
    assert system == SystemMessage(content=f"You are Writer. {note} GUIDE")


def test_a_group_of_two_names_the_other_alone() -> None:
    session = log_of(
        GroupMembersEvent(name="Launch", members=("Researcher", "Writer")),
        instructions("r", "Researcher"),
        TurnStart(turn=0, bot_id="r"),
    )

    system = runtime_over(ScriptedClient([])).request_messages(session)[0]

    assert "talking with the person and Writer. " in str(system.content)


def test_each_bot_keeps_its_own_selected_tools_and_approvals() -> None:
    session = log_of(
        *RESEARCHER_TURN,
        TurnStart(turn=1, bot_id="r"),
        ApprovalGrant(turn=1, tool="fs__write"),
        TurnStart(turn=2, bot_id="w"),
    )

    assert session.tools_selected() == ()
    assert session.tools_granted() == frozenset()
    session.append(TurnStart(turn=3, bot_id="r"))
    assert session.tools_selected() == ("web__get",)
    assert session.tools_granted() == {"fs__write"}


def test_a_call_is_answered_for_the_bot_whose_turn_asked_it() -> None:
    session = log_of(*RESEARCHER_TURN, TurnStart(turn=1, bot_id="w"))

    assert session.speaker_of_call("c1") == "r"
    assert session.speaker_id() == "w"


def test_instructions_logged_before_groups_count_as_any_bot_s() -> None:
    older = BotInstructionsEvent(name="Researcher", instructions="Cite.")
    session = log_of(older, instructions("w", "Writer"))

    assert session.bot_instructions("r") == older
    assert session.bot_instructions("w") == instructions("w", "Writer")
