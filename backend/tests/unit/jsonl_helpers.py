"""Builders for the JSONL backend's tests: a header, a turn, a repository."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from harness.llm.messages import AssistantMessage, UserMessage
from harness.llm.stream import TextChunk
from harness.session.models import (
    AssistantChunk,
    AssistantMessageEvent,
    SessionHeader,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)
from harness.session.repositories.jsonl import JsonlSessionRepository


def header(session_id: str = "s") -> SessionHeader:
    return SessionHeader(id=session_id, created_at=datetime(2026, 1, 1, tzinfo=UTC))


def a_turn(turn: int = 0, *, text: str = "hi") -> list:
    return [
        TurnStart(turn=turn),
        UserMessageEvent(turn=turn, message=UserMessage(content=text)),
        AssistantChunk(turn=turn, step=0, chunk=TextChunk(text="ok")),
        AssistantMessageEvent(turn=turn, step=0, message=AssistantMessage(content="ok")),
        TurnEnd(turn=turn, reason="completed"),
    ]


def repository(tmp_path: Path) -> JsonlSessionRepository:
    return JsonlSessionRepository(tmp_path / "sessions")
