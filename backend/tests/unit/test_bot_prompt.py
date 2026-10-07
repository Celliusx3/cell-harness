"""Assistant's request is what the one agent's was before bots existed."""

from __future__ import annotations

from datetime import UTC, datetime

from harness.bots import ASSISTANT_INSTRUCTIONS
from harness.session.log import Session
from harness.session.models import BotInstructionsEvent, SessionHeader
from harness.tools.native.code import CODE_PROMPT
from harness.web.agent import GUIDANCE
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import agent_over

PROMPT_BEFORE_BOTS = (
    "You are a helpful assistant. When a tool can answer the user's question, "
    "call it instead of guessing. You have a long-term memory in the memory "
    "functions: search it before answering about anything the user told you in "
    "an earlier conversation, and save what they ask you to remember."
) + CODE_PROMPT


def test_assistant_s_system_prompt_is_byte_for_byte_the_one_before_bots() -> None:
    agent = agent_over(ScriptedClient(completed("x")), system_prompt=GUIDANCE)
    session = Session(SessionHeader(id="s", created_at=datetime(2026, 1, 1, tzinfo=UTC)))
    session.append(BotInstructionsEvent(name="Assistant", instructions=ASSISTANT_INSTRUCTIONS))

    system = agent.request_messages(session)[0]

    assert system.content == PROMPT_BEFORE_BOTS


def test_a_session_with_no_instructions_logged_keeps_the_agent_s_own_prompt() -> None:
    agent = agent_over(ScriptedClient(completed("x")), system_prompt="only this")
    session = Session(SessionHeader(id="s", created_at=datetime(2026, 1, 1, tzinfo=UTC)))

    system = agent.request_messages(session)[0]

    assert system.content == "only this"
