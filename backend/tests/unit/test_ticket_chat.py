"""A ticket keeps the chat it came from; one saved before that reads as its bot's own chat."""

from __future__ import annotations

from datetime import UTC, datetime

from harness.tickets.domain.models import Ticket, TicketsFile, ticket_chat_id

STORED_BEFORE = {
    "id": "t1",
    "bot_id": "translator",
    "title": "Translate",
    "task": "Translate it.",
    "state": "done",
    "created_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
}


def test_a_ticket_from_a_group_is_the_groups() -> None:
    ticket = Ticket.model_validate({**STORED_BEFORE, "chat_id": "group-1"})

    assert ticket_chat_id(ticket, chat_of=lambda bot_id: bot_id) == "group-1"


def test_a_ticket_saved_before_chats_were_kept_is_its_bots() -> None:
    (ticket,) = TicketsFile.model_validate({"tickets": [STORED_BEFORE]}).tickets

    assert (
        ticket_chat_id(ticket, chat_of=lambda bot_id: f"chat-of-{bot_id}") == "chat-of-translator"
    )
