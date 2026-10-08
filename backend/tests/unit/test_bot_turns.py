"""A bot's turns, and its compactions, are prompted with the instructions its chat logged last."""

from __future__ import annotations

import asyncio
from pathlib import Path

from harness.bots import ASSISTANT_ID, BotService
from harness.llm.messages import ApplicationMessage, SystemMessage, UserMessage
from harness.runs.service import RunService
from harness.session.compaction import CompactionEnd
from harness.session.log import Session
from harness.session.models import BotInstructionsEvent, TurnStart, UserMessageEvent
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
    bots.update(ASSISTANT_ID, "Assistant", "Be brief.")

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
    bots.update(ASSISTANT_ID, "Assistant", "Be brief.")

    await asyncio.wait_for(runs.resume(session, "c1", Ok(content="here"))._outer, timeout=5)

    assert client.seen[0] == SystemMessage(content="Be kind.")
    assert _logged(session) == ["Be kind."]
