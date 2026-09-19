"""Request and response bodies."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from harness.session.models import SessionEvent


class ConversationSummary(BaseModel):
    """One row of the conversation list."""

    model_config = ConfigDict(frozen=True)

    id: str
    created_at: datetime
    title: str


class ConversationDetail(ConversationSummary):
    """A conversation's whole log, and where to pick up streaming from."""

    events: list[SessionEvent]
    next_cursor: int
    running: bool


class MessageAccepted(ConversationSummary):
    """What `POST /{id}/messages` answers with."""

    queued: bool


class SendMessage(BaseModel):
    """A message starting a turn."""

    model_config = ConfigDict(frozen=True)

    prompt: str = Field(min_length=1)

    @field_validator("prompt")
    @classmethod
    def _not_only_whitespace(cls, value: str) -> str:
        """Reject a prompt that is blank once you look at it."""
        if not value.strip():
            raise ValueError("prompt must not be blank")
        return value
