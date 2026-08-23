"""The log and the history derived from it."""

from __future__ import annotations

from harness.llm.messages import AssistantMessage, UserMessage
from harness.llm.stream import Completed, TextChunk
from harness.session.derive import derive_messages
from harness.session.events import (
    AssistantChunk,
    AssistantMessageEvent,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)
from harness.session.log import Session


def test_sequence_numbers_are_contiguous_from_zero() -> None:
    """A cursor is only a complete answer if nothing can be missing between two.

    Phase 4's run subscription depends on it.
    """
    session = Session("s")
    seqs = [session.append(TurnStart(turn=n)) for n in range(5)]
    assert seqs == [0, 1, 2, 3, 4]


def test_after_returns_everything_past_a_cursor() -> None:
    session = Session("s")
    for n in range(4):
        session.append(TurnStart(turn=n))

    assert [e.turn for e in session.after(1)] == [2, 3]
    assert len(session.after(-1)) == 4
    assert session.after(3) == []


def test_next_turn_is_derived_not_counted() -> None:
    """No counter to restore when a session is rehydrated in phase 3."""
    session = Session("s")
    assert session.next_turn() == 0

    session.append(TurnStart(turn=0))
    session.append(TurnEnd(turn=0, reason="completed"))
    assert session.next_turn() == 1


def test_every_event_round_trips_as_json() -> None:
    """The closed union of concretely-typed models is what makes the log
    losslessly persistable in phase 3 without a runtime check on every append."""
    session = Session("s")
    session.append(TurnStart(turn=0))
    session.append(UserMessageEvent(turn=0, message=UserMessage(content="hi")))
    session.append(AssistantChunk(turn=0, chunk=TextChunk(text="he")))
    session.append(AssistantChunk(turn=0, chunk=Completed(full_text="hello")))
    session.append(AssistantMessageEvent(turn=0, message=AssistantMessage(content="hello")))
    session.append(TurnEnd(turn=0, reason="completed"))

    for event in session.events():
        assert type(event).model_validate_json(event.model_dump_json()) == event


def test_derive_skips_chunks_and_turn_boundaries() -> None:
    session = Session("s")
    session.append(TurnStart(turn=0))
    session.append(UserMessageEvent(turn=0, message=UserMessage(content="hi")))
    session.append(AssistantChunk(turn=0, chunk=TextChunk(text="he")))
    session.append(AssistantChunk(turn=0, chunk=TextChunk(text="llo")))
    session.append(AssistantMessageEvent(turn=0, message=AssistantMessage(content="hello")))
    session.append(TurnEnd(turn=0, reason="completed"))

    assert derive_messages(session.events()) == [
        UserMessage(content="hi"),
        AssistantMessage(content="hello"),
    ]


def test_chunks_reassemble_to_the_logged_message() -> None:
    """Acceptance: replay from the log reproduces the same reply.

    The chunks are what a UI redraws token by token; the assembled message is
    what the model is shown. If they can disagree, a reattached client sees
    something the next turn's context denies.
    """
    session = Session("s")
    session.append(TurnStart(turn=0))
    session.append(UserMessageEvent(turn=0, message=UserMessage(content="hi")))
    for piece in ("he", "ll", "o"):
        session.append(AssistantChunk(turn=0, chunk=TextChunk(text=piece)))
    session.append(AssistantMessageEvent(turn=0, message=AssistantMessage(content="hello")))

    replayed = "".join(
        e.chunk.text
        for e in session.events()
        if isinstance(e, AssistantChunk) and isinstance(e.chunk, TextChunk)
    )
    derived = derive_messages(session.events())[-1]
    assert replayed == derived.content


def test_no_system_message_is_ever_derived() -> None:
    """It is prepended per request, so it must not arrive from history too —
    otherwise a routed turn would carry the previous agent's prompt."""
    session = Session("s")
    session.append(UserMessageEvent(turn=0, message=UserMessage(content="hi")))

    assert all(m.role != "system" for m in derive_messages(session.events()))


def test_an_interrupted_reply_stays_in_history() -> None:
    """The user read it; hiding it would make the next turn's context disagree
    with what is on screen."""
    session = Session("s")
    session.append(UserMessageEvent(turn=0, message=UserMessage(content="hi")))
    session.append(
        AssistantMessageEvent(turn=0, message=AssistantMessage(content="par"), interrupted=True)
    )

    assert derive_messages(session.events())[-1] == AssistantMessage(content="par")
