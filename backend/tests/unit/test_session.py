"""The log and the history derived from it."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import get_args

from harness.llm.messages import ApplicationMessage, AssistantMessage, Message, UserMessage
from harness.llm.stream import Completed, TextChunk
from harness.session.derive import derive_messages
from harness.session.log import Session
from harness.session.models import (
    ApplicationMessageEvent,
    AssistantChunk,
    AssistantMessageEvent,
    SessionHeader,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)
from tests.unit.helpers import new_session


def test_sequence_numbers_are_contiguous_from_zero() -> None:
    session = new_session()
    seqs = [session.append(TurnStart(turn=n)) for n in range(5)]
    assert seqs == [0, 1, 2, 3, 4]


def test_numbers_carry_on_from_the_header() -> None:
    header = SessionHeader(id="s", created_at=datetime(2026, 1, 1, tzinfo=UTC), numbered_from=10)
    events = [TurnStart(turn=n) for n in range(3)]
    session = Session(header, events)

    assert session.numbered_events_from(3) == [(10, events[0]), (11, events[1]), (12, events[2])]
    assert session.numbered_events_from(11) == [(11, events[1]), (12, events[2])]
    assert session.next_number() == 13


def test_next_turn_is_derived_not_counted() -> None:
    session = new_session()
    assert session.next_turn() == 0

    session.append(TurnStart(turn=0))
    session.append(TurnEnd(turn=0, reason="completed"))
    assert session.next_turn() == 1


def test_every_event_round_trips_as_json() -> None:
    session = new_session()
    session.append(TurnStart(turn=0))
    session.append(UserMessageEvent(turn=0, message=UserMessage(content="hi")))
    session.append(AssistantChunk(turn=0, step=0, chunk=TextChunk(text="he")))
    session.append(AssistantChunk(turn=0, step=0, chunk=Completed(full_text="hello")))
    session.append(AssistantMessageEvent(turn=0, step=0, message=AssistantMessage(content="hello")))
    session.append(TurnEnd(turn=0, reason="completed"))

    for event in session.events():
        assert type(event).model_validate_json(event.model_dump_json()) == event


def test_derive_skips_chunks_and_turn_boundaries() -> None:
    session = new_session()
    session.append(TurnStart(turn=0))
    session.append(UserMessageEvent(turn=0, message=UserMessage(content="hi")))
    session.append(AssistantChunk(turn=0, step=0, chunk=TextChunk(text="he")))
    session.append(AssistantChunk(turn=0, step=0, chunk=TextChunk(text="llo")))
    session.append(AssistantMessageEvent(turn=0, step=0, message=AssistantMessage(content="hello")))
    session.append(TurnEnd(turn=0, reason="completed"))

    assert derive_messages(session.events()) == [
        UserMessage(content="hi"),
        AssistantMessage(content="hello"),
    ]


def test_chunks_reassemble_to_the_logged_message() -> None:
    session = new_session()
    session.append(TurnStart(turn=0))
    session.append(UserMessageEvent(turn=0, message=UserMessage(content="hi")))
    for piece in ("he", "ll", "o"):
        session.append(AssistantChunk(turn=0, step=0, chunk=TextChunk(text=piece)))
    session.append(AssistantMessageEvent(turn=0, step=0, message=AssistantMessage(content="hello")))

    replayed = "".join(
        e.chunk.text
        for e in session.events()
        if isinstance(e, AssistantChunk) and isinstance(e.chunk, TextChunk)
    )
    derived = derive_messages(session.events())[-1]
    assert replayed == derived.content


def test_no_system_message_is_ever_derived() -> None:
    session = new_session()
    session.append(UserMessageEvent(turn=0, message=UserMessage(content="hi")))

    assert all(m.role != "system" for m in derive_messages(session.events()))


def test_an_interrupted_reply_stays_in_history() -> None:
    session = new_session()
    session.append(UserMessageEvent(turn=0, message=UserMessage(content="hi")))
    session.append(
        AssistantMessageEvent(
            turn=0, step=0, message=AssistantMessage(content="par"), interrupted=True
        )
    )

    assert derive_messages(session.events())[-1] == AssistantMessage(content="par")


def test_an_application_message_is_a_user_message_on_the_wire() -> None:
    session = new_session()
    session.append(ApplicationMessageEvent(turn=0, message=ApplicationMessage(content="Note: …")))

    assert derive_messages(session.events()) == [UserMessage(content="Note: …")]


def test_an_application_message_is_not_a_wire_message() -> None:
    assert ApplicationMessage not in get_args(Message)
