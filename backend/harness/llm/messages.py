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


class ToolCall(BaseModel):
    """One invocation the model asked for.

    `arguments` is the model's raw JSON **string**, kept unparsed. Two reasons:
    replay has to reproduce exactly what the model emitted, and arguments that
    fail to parse are a normal tool failure the model can recover from — storing
    a parsed dict would mean the log could not hold the call that caused it.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    arguments: str


class ToolSpec(BaseModel):
    """What the model is told about one tool.

    Exactly the three fields that go on the wire. `ToolDefinition` holds more —
    an executor, a timeout, a parser — and `ToolDefinition.spec()` is the
    allowlist that keeps them out of a request.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    input_schema: dict


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
    """One assembled model reply, and any tool calls it asked for.

    A reply may carry text, tool calls, or both — a model often narrates ("Let
    me check the time…") before calling something.

    A tuple rather than a list because the model is frozen, and a mutable default
    on a shared frozen value is the classic way for two messages to end up
    sharing one list.
    """

    model_config = ConfigDict(frozen=True)

    role: Literal["assistant"] = "assistant"
    content: str
    tool_calls: tuple[ToolCall, ...] = ()


class ToolMessage(BaseModel):
    """What one tool call returned, addressed back to it by `tool_call_id`.

    Providers require **exactly one** of these per tool call in the preceding
    assistant message — a call with no result makes the next request invalid, not
    merely incomplete. That is why the loop writes one on every path, including
    refusals and interruptions.
    """

    model_config = ConfigDict(frozen=True)

    role: Literal["tool"] = "tool"
    tool_call_id: str
    content: str


Message = SystemMessage | UserMessage | AssistantMessage | ToolMessage
