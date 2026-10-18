"""Who speaks next: the person's mentions queue the bots, and theirs bring others back."""

from __future__ import annotations

import pytest

from harness.bots import Bot
from harness.bots._turn_order import (
    MAX_TURNS_FROM_MENTIONS,
    first_speakers,
    is_mentioned,
    next_speaker,
)
from harness.llm.messages import AssistantMessage, UserMessage
from harness.session.models import (
    AssistantMessageEvent,
    SessionEvent,
    TurnEnd,
    TurnEndReason,
    TurnStart,
    UserMessageEvent,
)
from harness.skills.invocation import MARKER

R = Bot(id="r", name="Researcher", instructions="Cite.")
W = Bot(id="w", name="Writer", instructions="Write.")
E = Bot(id="e", name="Copy Editor", instructions="Edit.")
TEAM = (R, W, E)


def turn(
    number: int, bot: Bot, said: str, reason: TurnEndReason = "completed"
) -> list[SessionEvent]:
    """One turn by `bot` that says `said` and ends for `reason`."""
    return [
        TurnStart(turn=number, bot_id=bot.id),
        AssistantMessageEvent(turn=number, step=0, message=AssistantMessage(content=said)),
        TurnEnd(turn=number, reason=reason),
    ]


def opened_by(text: str, events: list[SessionEvent]) -> list[SessionEvent]:
    """A turn's `events` with the person's `text` as the message that opened it."""
    start, *rest = events
    assert isinstance(start, TurnStart)
    return [start, UserMessageEvent(turn=start.turn, message=UserMessage(content=text)), *rest]


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("@Writer go", "Writer"),
        ("thanks @writer!", "Writer"),
        ("(@WRITER)", "Writer"),
        ("ask @Copy Editor, please", "Copy Editor"),
        ("@Writer", "Writer"),
    ],
)
def test_a_mention_is_at_and_the_whole_name_in_any_case(text: str, name: str) -> None:
    assert is_mentioned(text, name)


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("mail me at me@Writer", "Writer"),
        ("@Writers", "Writer"),
        ("@Writer-bot", "Writer"),
        ("@Writer_2", "Writer"),
        ("Writer, go", "Writer"),
        ("@Copy", "Copy Editor"),
        ("@ ", " "),
    ],
)
def test_no_mention_inside_a_word_or_a_longer_name(text: str, name: str) -> None:
    assert not is_mentioned(text, name)


def test_the_person_queues_the_members_they_mention_in_member_order() -> None:
    assert first_speakers("@Copy Editor then @Researcher", TEAM) == (R, E)


@pytest.mark.parametrize(
    "text", ["what now?", "@everyone what now?", "@Writer and @everyone, go", "@Nobody here?"]
)
def test_mentioning_everyone_or_no_member_queues_every_member(text: str) -> None:
    assert first_speakers(text, TEAM) == TEAM


def test_each_member_in_the_queue_speaks_in_turn() -> None:
    log = opened_by("go", turn(0, R, "Sources."))

    assert next_speaker(log, TEAM) == W
    assert next_speaker([*log, *turn(1, W, "Draft.")], TEAM) == E
    assert next_speaker([*log, *turn(1, W, "Draft."), *turn(2, E, "Edited.")], TEAM) is None


def test_a_mention_brings_back_a_member_who_already_spoke() -> None:
    log = [
        *opened_by("@Researcher @Writer", turn(0, R, "Sources.")),
        *turn(1, W, "@Researcher sure?"),
    ]

    assert next_speaker(log, TEAM) == R


def test_a_bot_never_queues_itself_nor_a_member_already_waiting() -> None:
    log = opened_by("@Researcher @Writer", turn(0, R, "@Researcher and @Writer, over to you."))

    assert next_speaker(log, TEAM) == W
    assert next_speaker([*log, *turn(1, W, "Done.")], TEAM) is None


def test_mentions_add_at_most_six_turns_per_message_of_the_person_s() -> None:
    pair = (R, W)
    log = opened_by("go", turn(0, R, "Over to you @Researcher @Writer."))
    speakers = [R]
    while (speaker := next_speaker(log, pair)) is not None:
        speakers.append(speaker)
        log = [*log, *turn(len(speakers) - 1, speaker, "Over to you @Researcher @Writer.")]

    assert len(speakers) == 2 + MAX_TURNS_FROM_MENTIONS
    assert speakers == [R, W] * 4


def test_a_new_message_from_the_person_starts_a_new_queue() -> None:
    log = [*opened_by("@Researcher", turn(0, R, "Hi @Writer")), *turn(1, W, "Hi.")]

    assert next_speaker([*log, *opened_by("@Copy Editor @Writer", turn(2, W, "Yes."))], TEAM) == E


@pytest.mark.parametrize("reason", ["pending", "failed", "cancelled"])
def test_the_queue_stops_at_a_turn_that_did_not_complete(reason: TurnEndReason) -> None:
    assert next_speaker(opened_by("go", turn(0, R, "Asking.", reason)), TEAM) is None


def test_the_queue_carries_on_once_the_answered_bot_completes() -> None:
    asked = opened_by("@Researcher @Writer", turn(0, R, "Which year, @Copy Editor?", "pending"))
    answered = [*asked, *turn(1, R, "2024 it is.")]

    assert next_speaker(answered, TEAM) == W
    assert next_speaker([*answered, *turn(2, W, "Posted.")], TEAM) == E


def test_nobody_is_next_while_a_turn_is_open_or_before_anyone_spoke() -> None:
    assert next_speaker(opened_by("go", turn(0, R, "Sources."))[:-1], TEAM) is None
    assert next_speaker([], TEAM) is None


def test_a_bot_s_own_chat_is_a_group_of_one_that_ends_after_its_turn() -> None:
    assert first_speakers("hi @Writer", (R,)) == (R,)
    assert next_speaker(opened_by("hi", turn(0, R, "Hello @Researcher.")), (R,)) is None


def test_a_skill_message_is_answered_by_whom_the_person_typed_not_by_the_skill_text() -> None:
    expanded = f'/brief{MARKER}brief">Hand the draft to @Writer.</skill>'

    assert first_speakers(expanded, TEAM) == TEAM
    assert first_speakers(f'/brief @Copy Editor{MARKER}brief">@Writer</skill>', TEAM) == (E,)
