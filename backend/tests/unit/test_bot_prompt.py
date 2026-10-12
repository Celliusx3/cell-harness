"""Assistant's request is what the one runtime's was before bots existed."""

from __future__ import annotations

from datetime import UTC, datetime

from harness.llm.messages import (
    ApplicationMessage,
    AssistantMessage,
    SystemMessage,
    Text,
    ToolCall,
    ToolMessage,
    ToolReference,
    UserMessage,
)
from harness.prompts import ASSISTANT_INSTRUCTIONS, CODE_PROMPT, GUIDANCE
from harness.session.log import Session
from harness.session.models import (
    ApplicationMessageEvent,
    ApprovalGrant,
    AssistantMessageEvent,
    BotInstructionsEvent,
    SessionHeader,
    StepEnd,
    StepStart,
    ToolCallEvent,
    ToolResultEvent,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import runtime_over

PROMPT_BEFORE_BOTS = (
    "You are a helpful assistant. When a tool can answer the user's question, "
    "call it instead of guessing. You have a long-term memory in the memory "
    "functions: search it before answering about anything the user told you in "
    "an earlier conversation, and save what they ask you to remember."
) + CODE_PROMPT


def test_assistant_s_system_prompt_is_byte_for_byte_the_one_before_bots() -> None:
    runtime = runtime_over(ScriptedClient(completed("x")), guidance=GUIDANCE)
    session = Session(SessionHeader(id="s", created_at=datetime(2026, 1, 1, tzinfo=UTC)))
    session.append(BotInstructionsEvent(name="Assistant", instructions=ASSISTANT_INSTRUCTIONS))

    system = runtime.request_messages(session)[0]

    assert system.content == PROMPT_BEFORE_BOTS


def test_a_session_with_no_instructions_logged_keeps_the_agent_s_own_prompt() -> None:
    runtime = runtime_over(ScriptedClient(completed("x")), guidance="only this")
    session = Session(SessionHeader(id="s", created_at=datetime(2026, 1, 1, tzinfo=UTC)))

    system = runtime.request_messages(session)[0]

    assert system.content == "only this"


CALL = ToolCall(id="c1", name="fs__write", arguments='{"path": "a"}')


def _bot_s_own_chat(bot_id: str | None) -> Session:
    """One bot's chat: a tool it selected, a note, an approval, a pending call it was answered."""
    session = Session(SessionHeader(id="r1", created_at=datetime(2026, 1, 1, tzinfo=UTC)))
    for event in (
        BotInstructionsEvent(name="Researcher", instructions="Cite.", bot_id=bot_id),
        TurnStart(turn=0, bot_id=bot_id),
        UserMessageEvent(turn=0, message=UserMessage(content="find a source")),
        StepStart(turn=0, step=0),
        AssistantMessageEvent(
            turn=0, step=0, message=AssistantMessage(content="Looking.", tool_calls=(CALL,))
        ),
        ToolCallEvent(turn=0, step=0, call=CALL),
        ToolResultEvent(
            turn=0,
            step=0,
            message=ToolMessage(
                tool_call_id="c1", content=(Text(text="ok"), ToolReference(tool_name="web__get"))
            ),
        ),
        StepEnd(turn=0, step=0),
        ApplicationMessageEvent(turn=0, message=ApplicationMessage(content="a reminder")),
        StepStart(turn=0, step=1),
        AssistantMessageEvent(turn=0, step=1, message=AssistantMessage(content="NO_RESPONSE")),
        StepEnd(turn=0, step=1),
        TurnEnd(turn=0, reason="completed"),
        TurnStart(turn=1, bot_id=bot_id),
        ApprovalGrant(turn=1, tool="fs__write"),
        UserMessageEvent(turn=1, message=UserMessage(content="and another")),
        StepStart(turn=1, step=0),
        AssistantMessageEvent(turn=1, step=0, message=AssistantMessage(content="Here.")),
        StepEnd(turn=1, step=0),
        TurnEnd(turn=1, reason="completed"),
    ):
        session.append(event)
    return session


def test_a_bot_s_own_chat_sends_the_same_request_once_its_events_carry_its_id() -> None:
    runtime = runtime_over(ScriptedClient(completed("x")), guidance="GUIDE")
    before_groups = _bot_s_own_chat(None)
    with_ids = _bot_s_own_chat("r1")

    assert (
        runtime.request_messages(with_ids)
        == runtime.request_messages(before_groups)
        == [
            SystemMessage(content="Cite. GUIDE"),
            UserMessage(content="find a source"),
            AssistantMessage(content="Looking.", tool_calls=(CALL,)),
            ToolMessage(
                tool_call_id="c1", content=(Text(text="ok"), ToolReference(tool_name="web__get"))
            ),
            UserMessage(content="a reminder"),
            AssistantMessage(content="NO_RESPONSE"),
            UserMessage(content="and another"),
            AssistantMessage(content="Here."),
        ]
    )
    assert with_ids.tools_selected() == before_groups.tools_selected() == ("web__get",)
    assert with_ids.tools_granted() == before_groups.tools_granted() == {"fs__write"}
