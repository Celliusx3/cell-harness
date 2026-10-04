"""Which provider errors the loop can do something about."""

from __future__ import annotations

from harness.llm.stream import CONTEXT_WINDOW_EXCEEDED

_OVERFLOW_WORDING = (
    "context_length_exceeded",
    "context length exceeded",
    "maximum context length",
    "maximum context limit",
    "exceeds the available context size",
    "longer than the model's context length",
    "exceeds the maximum number of tokens allowed",
    "exceed context limit",
    "prompt is too long",
)


def classify(body: str) -> str | None:
    """`CONTEXT_WINDOW_EXCEEDED` when an error body says the request outgrew the window."""
    text = body.lower()
    if any(wording in text for wording in _OVERFLOW_WORDING):
        return CONTEXT_WINDOW_EXCEEDED
    return None
