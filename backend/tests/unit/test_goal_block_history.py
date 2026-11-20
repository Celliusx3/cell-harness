"""A lead's `<goal>` block stays in the log but never reaches any bot's history."""

from __future__ import annotations

from harness.llm import AssistantMessage, UserMessage
from harness.session.domain.model_history import derive_messages
from harness.session.domain.models import (
    AssistantMessageEvent,
    BotInstructionsEvent,
    SessionEvent,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)

HANDED_OVER = 'Over to Bull.\n\n<goal>{"status":"continue","next":"Bull","task":"Argue"}</goal>'
ONLY_A_BLOCK = '<goal>{"status":"done","detail":"Verdicts posted."}</goal>'


def turn(number: int, bot_id: str, asked: str, said: str) -> list[SessionEvent]:
    return [
        TurnStart(turn=number, bot_id=bot_id),
        UserMessageEvent(turn=number, message=UserMessage(content=asked)),
        AssistantMessageEvent(turn=number, step=0, message=AssistantMessage(content=said)),
        TurnEnd(turn=number, reason="completed"),
    ]


def named(bot_id: str, name: str) -> BotInstructionsEvent:
    return BotInstructionsEvent(bot_id=bot_id, name=name, instructions="")


def test_the_lead_sees_its_own_reply_without_the_block() -> None:
    log = [
        *turn(0, "judge", "/goal pick one", HANDED_OVER),
        *turn(1, "judge", "Can u check with others?", "Sure."),
    ]

    assert derive_messages(log)[:2] == [
        UserMessage(content="/goal pick one"),
        AssistantMessage(content="Over to Bull."),
    ]


def test_another_bot_hears_the_lead_without_the_block() -> None:
    log = [
        named("judge", "Judge"),
        *turn(0, "judge", "/goal pick one", HANDED_OVER),
        *turn(1, "bull", "go", "Buy NFLX."),
    ]

    assert derive_messages(log)[1] == UserMessage(content='<speaker name="Judge" />\nOver to Bull.')


def test_a_reply_that_was_only_a_block_is_not_heard() -> None:
    log = [
        named("judge", "Judge"),
        *turn(0, "judge", "/goal pick one", ONLY_A_BLOCK),
        *turn(1, "bull", "go", "Buy NFLX."),
    ]

    assert derive_messages(log)[:2] == [
        UserMessage(content="/goal pick one"),
        UserMessage(content="go"),
    ]
