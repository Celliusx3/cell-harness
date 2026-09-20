"""The end-of-step hook: an empty reply is told once, then the turn gives up."""

from __future__ import annotations

from harness.agent.hooks import GiveUp, Tell
from harness.agent.hooks.native.empty_reply import EMPTY_REPLY, EMPTY_REPLY_NOTE
from harness.llm.messages import AssistantMessage, ToolCall
from harness.session.log import Session
from harness.session.models import AssistantMessageEvent, TurnStart
from tests.unit.test_hooks_native import GUARD, call, turn


def replied(session: Session, text: str = "", *, calls: tuple[ToolCall, ...] = ()) -> None:
    session.append(
        AssistantMessageEvent(
            turn=0, step=0, message=AssistantMessage(content=text, tool_calls=calls)
        )
    )


async def test_the_first_empty_reply_is_told_and_the_second_gives_up() -> None:
    session = turn()
    assert await GUARD.end_of_step(session=session) is None

    replied(session)
    assert await GUARD.end_of_step(session=session) == Tell(EMPTY_REPLY_NOTE)

    replied(session)
    assert await GUARD.end_of_step(session=session) == GiveUp(EMPTY_REPLY)


async def test_an_empty_text_reply_that_calls_a_tool_is_not_an_empty_reply() -> None:
    session = turn()
    replied(session, calls=(call(),))
    replied(session, "  ")

    assert await GUARD.end_of_step(session=session) == Tell(EMPTY_REPLY_NOTE)


async def test_a_reply_cut_off_mid_stream_is_not_an_empty_reply() -> None:
    session = turn()
    session.append(
        AssistantMessageEvent(
            turn=0, step=0, message=AssistantMessage(content=""), interrupted=True
        )
    )

    assert await GUARD.end_of_step(session=session) is None


async def test_the_empty_count_starts_over_each_turn() -> None:
    session = turn()
    replied(session)
    replied(session)
    session.append(TurnStart(turn=1))

    assert await GUARD.end_of_step(session=session) is None


async def test_a_reply_with_text_ends_the_run_of_empty_replies() -> None:
    session = turn()
    replied(session)
    replied(session, "here you go")

    assert await GUARD.end_of_step(session=session) is None
