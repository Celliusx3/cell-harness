"""Request and response bodies.

Typed in both directions, per the house rule: a response model is what stops a
field being added to an internal type and silently appearing on the wire — the
same argument as the tool-schema allowlist.

**Events go out as themselves.** `SessionEvent` is the wire type, so there is no
translation layer here to keep in step with `session/models.py` and no second
shape for a UI to learn. A new event type is a frontend renderer and nothing else.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from harness.session.models import SessionEvent


class ConversationSummary(BaseModel):
    """One row of the conversation list.

    Returned by both POST paths too: creating or continuing a conversation hands
    back the same shape the sidebar renders, so a client never has to re-fetch to
    learn the title that was just stamped.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    created_at: datetime
    # Stamped from the first user message at first flush, so it is empty for a
    # conversation whose opening turn has not checkpointed yet. A client needs a
    # fallback; it is not a guarantee.
    title: str


class ConversationDetail(ConversationSummary):
    """A conversation's whole log, and where to pick up streaming from."""

    events: list[SessionEvent]
    # The cursor to open the event stream at. Equal to `len(events)`, and sent
    # explicitly rather than left for the client to compute — the one number that
    # must agree between snapshot and stream should be stated by whoever knows it.
    next_cursor: int
    # Whether a turn is in flight. The *only* status the wire carries: how a turn
    # ended is the `reason` on its `turn/end`, which is already in `events`, so
    # duplicating it here would create a second answer to one question.
    running: bool


class SendMessage(BaseModel):
    """A message starting a turn."""

    model_config = ConfigDict(frozen=True)

    # Validated at the edge: a blank prompt is a `422`, never a turn that asks the
    # model nothing and bills for it.
    prompt: str = Field(min_length=1)

    @field_validator("prompt")
    @classmethod
    def _not_only_whitespace(cls, value: str) -> str:
        """Reject a prompt that is blank once you look at it.

        `min_length` counts characters, so `"   "` satisfies it — a real
        possibility from a composer that trims nothing before sending.

        The value is returned **unmodified**. Stripping it here would quietly
        rewrite what someone typed, and trailing whitespace is meaningful inside a
        pasted code block; the check is whether anything is there, not what.
        """
        if not value.strip():
            raise ValueError("prompt must not be blank")
        return value
