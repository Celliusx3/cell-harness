"""The message vocabulary a model request is made of.

Three roles, one shared shape. This is deliberately *not* the session event
vocabulary: a `Message` is what goes on the wire to a provider, a `SessionEvent`
is what is durably recorded, and the two diverge as soon as anything is logged
that the model never sees (or seen that isn't a message — a tool schema, say).
`session.derive_messages` is the one place that turns the second into the first.

A user or assistant `content` is a plain string. A **tool result's** is a list
of typed blocks — the Anthropic shape — because a result can carry more than
prose: a `tool_reference` says "this tool is callable now", and an image will be
a block when an MCP server returns one. The wire this harness speaks (OpenAI
`/chat/completions`) has no such blocks, so `adapters/openai.py` renders them to
the string it expects; what a block *means* is decided once, there.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    an executor, a parser — and `ToolDefinition.spec()` is the
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


class Text(BaseModel):
    """Prose in a tool result — what almost every result is, entirely."""

    model_config = ConfigDict(frozen=True)

    type: Literal["text"] = "text"
    text: str


class ToolReference(BaseModel):
    """A tool this result made callable by name.

    Anthropic's `tool_reference`: a discovery tool answers with references, and
    the platform expands them into the tool list on every request thereafter by
    reading them out of history. Here the harness is that platform — the
    pipeline puts the tool in the request, the adapter tells the model in words.
    """

    model_config = ConfigDict(frozen=True)

    type: Literal["tool_reference"] = "tool_reference"
    tool_name: str


# Discriminated on `type` like `SessionEvent`, so a stored result decodes with no
# new code and a new block kind is one union member.
Block = Annotated[Text | ToolReference, Field(discriminator="type")]


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
    content: tuple[Block, ...]

    @field_validator("content", mode="before")
    @classmethod
    def _wrap_text(cls, value: object) -> object:
        """A plain string is one text block. Every log written before blocks
        existed holds a string here, and most tools still return one."""
        return (Text(text=value),) if isinstance(value, str) else value

    @property
    def text(self) -> str:
        return render_text(self.content)


def render_text(blocks: tuple[Block, ...]) -> str:
    """The prose of a result: its text blocks, joined. References are not prose
    — what they say to the model is the adapter's to phrase."""
    return "\n\n".join(block.text for block in blocks if isinstance(block, Text))


Message = SystemMessage | UserMessage | AssistantMessage | ToolMessage
