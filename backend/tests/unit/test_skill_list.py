"""Step hooks' text on the first user message, and the hook that lists the skills."""

from __future__ import annotations

from pathlib import Path

from harness.llm import (
    ApplicationMessage,
    AssistantMessage,
    SystemMessage,
    UserMessage,
)
from harness.prompts import SKILL_LIST_INTRO
from harness.runtime.hooks.native.skill_list import SkillListHook
from harness.session.compaction import CompactionEnd
from harness.session.log import Session
from harness.session.models import (
    AssistantMessageEvent,
    StepEnd,
    StepStart,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import new_session, no_skills, runtime_over, skills_at

LIST = "The following skills are available for use with the skill tool:\n\n- pdf: PDF work."
REMINDED = f"\n\n<system-reminder>\n{LIST}\n</system-reminder>"
RUNTIME = runtime_over(ScriptedClient(completed("x")), guidance="GUIDE")


def two_turns(session: Session) -> Session:
    for turn, said in ((0, "first"), (1, "second")):
        session.append(TurnStart(turn=turn, bot_id="b"))
        session.append(UserMessageEvent(turn=turn, message=UserMessage(content=said)))
        session.append(StepStart(turn=turn, step=0))
        session.append(
            AssistantMessageEvent(turn=turn, step=0, message=AssistantMessage(content="ok"))
        )
        session.append(StepEnd(turn=turn, step=0))
        session.append(TurnEnd(turn=turn, reason="completed"))
    return session


def test_the_context_rides_on_the_first_user_message_only() -> None:
    session = two_turns(new_session())

    messages = RUNTIME.request_messages(session, (LIST,))

    assert messages == [
        SystemMessage(content="GUIDE"),
        UserMessage(content="first" + REMINDED),
        AssistantMessage(content="ok"),
        UserMessage(content="second"),
        AssistantMessage(content="ok"),
    ]


def test_each_text_is_its_own_system_reminder() -> None:
    session = two_turns(new_session())

    first = RUNTIME.request_messages(session, ("one", "two"))[1]

    assert first == UserMessage(
        content="first\n\n<system-reminder>\none\n</system-reminder>"
        "\n\n<system-reminder>\ntwo\n</system-reminder>"
    )


def test_after_compaction_the_context_rides_on_the_summary() -> None:
    session = two_turns(new_session())
    session.append(CompactionEnd(turn=None, message=ApplicationMessage(content="SUMMARY")))
    session.append(TurnStart(turn=2, bot_id="b"))
    session.append(UserMessageEvent(turn=2, message=UserMessage(content="third")))

    messages = RUNTIME.request_messages(session, (LIST,))

    assert messages == [
        SystemMessage(content="GUIDE"),
        UserMessage(content="SUMMARY" + REMINDED),
        UserMessage(content="third"),
    ]


def test_no_context_leaves_the_request_as_it_was() -> None:
    session = two_turns(new_session())

    assert RUNTIME.request_messages(session, ()) == RUNTIME.request_messages(session)


def test_the_log_keeps_only_what_was_typed() -> None:
    session = two_turns(new_session())

    RUNTIME.request_messages(session, (LIST,))

    typed = [e.message.content for e in session.events() if isinstance(e, UserMessageEvent)]
    assert typed == ["first", "second"]


async def test_the_hook_lists_the_skills_at_the_start_of_every_step(tmp_path: Path) -> None:
    (tmp_path / "pdf").mkdir()
    (tmp_path / "pdf" / "SKILL.md").write_text("---\ndescription: PDF work.\n---\nDo it.\n")

    listed = await SkillListHook(skills_at(tmp_path)).start_of_step()

    assert listed == f"{SKILL_LIST_INTRO}\n\n- pdf: PDF work."


async def test_with_no_skills_the_hook_says_nothing() -> None:
    assert await SkillListHook(no_skills()).start_of_step() is None
