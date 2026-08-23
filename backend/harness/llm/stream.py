"""What a streaming completion yields, event by event.

The contract every adapter owes: a stream yields zero or more `TextChunk`s and
then **exactly one** terminal event, `Completed` or `Failed`. The loop relies on
that to know a turn is over — an adapter that can end silently hangs it, and an
adapter that can yield two terminals makes "which one was it" unanswerable.

`Failed` is an event rather than an exception because a provider error is
ordinary, expected traffic on this channel: the loop reports it and the
conversation continues. Exceptions are reserved for our own bugs.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


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


class Completed(BaseModel):
    """Terminal: the model finished.

    `full_text` is the whole reply, not the last fragment — the adapter
    accumulates it so a consumer that ignored the chunks (a test, a non-streaming
    caller) still gets the answer, and so the loop never has to reassemble what
    the adapter already had.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["completed"] = "completed"
    full_text: str
    usage: Usage | None = None


class Failed(BaseModel):
    """Terminal: the call did not produce a reply.

    `reason` is model-facing and user-facing both, so it must be complete — no
    truncation, and enough detail to act on.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["failed"] = "failed"
    reason: str


StreamEvent = TextChunk | Completed | Failed
