"""What a streaming completion yields, event by event.

The contract every adapter owes: a stream yields zero or more `TextChunk`s and
`ToolCallChunk`s and then **exactly one** terminal event, `Completed` or
`Failed`. The loop relies on that to know a turn is over — an adapter that can
end silently hangs it, and an adapter that can yield two terminals makes "which
one was it" unanswerable.

`Failed` is an event rather than an exception because a provider error is
ordinary, expected traffic on this channel: the loop reports it and the
conversation continues. Exceptions are reserved for our own bugs.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from harness.llm.messages import ToolCall


class Usage(BaseModel):
    """Token accounting for one model call, when the provider reported it.

    Captured here rather than derived later because it travels with the response
    and nothing else can reconstruct it. Absent when the provider said nothing —
    an explicit `None`, not a zero, since "not reported" and "cost nothing" are
    different facts.
    """

    model_config = ConfigDict(frozen=True)

    input_tokens: int
    output_tokens: int


class TextChunk(BaseModel):
    """A fragment of the reply as it arrives."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["text"] = "text"
    text: str


class ToolCallChunk(BaseModel):
    """A tool call, once the adapter has assembled it.

    Providers stream a call in fragments — the name in one frame, the arguments
    across several more — so this is emitted when a call is *complete*, not per
    fragment. A half-built call is not a thing a consumer can do anything with.

    Live UX only: `Completed.tool_calls` is authoritative, exactly as `full_text`
    is authoritative over the `TextChunk`s. The duplication is what lets a UI
    show "calling clock…" before the turn ends.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["tool_call"] = "tool_call"
    call: ToolCall


class Completed(BaseModel):
    """Terminal: the model finished.

    `full_text` is the whole reply, not the last fragment — the adapter
    accumulates it so a consumer that ignored the chunks (a test, a non-streaming
    caller) still gets the answer, and so the loop never has to reassemble what
    the adapter already had. `tool_calls` is the same idea for calls.

    Both may be present: a model often narrates before calling something. Neither
    being present is also normal — a model may reply with nothing.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["completed"] = "completed"
    full_text: str
    tool_calls: tuple[ToolCall, ...] = ()
    usage: Usage | None = None


class Failed(BaseModel):
    """Terminal: the call did not produce a reply.

    `reason` is model-facing and user-facing both, so it must be complete — no
    truncation, and enough detail to act on.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["failed"] = "failed"
    reason: str


StreamEvent = TextChunk | ToolCallChunk | Completed | Failed
