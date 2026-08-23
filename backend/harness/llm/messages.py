"""The message vocabulary a model request is made of.

Three roles, one shared shape. This is deliberately *not* the session event
vocabulary: a `Message` is what goes on the wire to a provider, a `SessionEvent`
is what is durably recorded, and the two diverge as soon as anything is logged
that the model never sees (or seen that isn't a message — a tool schema, say).
`session.derive_messages` is the one place that turns the second into the first.

`content` is a plain string rather than a list of content blocks. Blocks arrive
when something needs them — an image attachment, a tool result with structured
parts — and adding a union member then is additive. Modelling them now would be
structure with no second variant to justify it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class SystemMessage(BaseModel):
    """The instructions prepended to a request.

    Never stored in the session log and never appended to history — the loop
    prepends it per request, which is what lets it reflect the agent running
    *this* turn rather than whatever was true when the conversation began.
    """

    model_config = ConfigDict(frozen=True)

    role: Literal["system"] = "system"
    content: str


class UserMessage(BaseModel):
    """A message on the model-visible surface attributed to the user.

    Covers a direct human prompt now; later it also carries synthetic context the
    harness injects (file-change notices, skill catalogs). Those are the same
    role on the wire, which is why the distinction lives on the session event's
    `source` rather than here.
    """

    model_config = ConfigDict(frozen=True)

    role: Literal["user"] = "user"
    content: str


class AssistantMessage(BaseModel):
    """One assembled model reply."""

    model_config = ConfigDict(frozen=True)

    role: Literal["assistant"] = "assistant"
    content: str


Message = SystemMessage | UserMessage | AssistantMessage
