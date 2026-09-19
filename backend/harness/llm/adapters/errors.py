"""Which provider errors the loop can do something about."""

from __future__ import annotations

import json

from harness.llm.stream import CONTEXT_WINDOW_EXCEEDED

_CODE = "context_length_exceeded"
_LM_STUDIO = "context length exceeded"


def classify(body: str) -> str | None:
    """The typed code for a 4xx body the loop can act on, or `None`."""
    try:
        payload = json.loads(body)
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    if isinstance(error, dict) and error.get("code") == _CODE:
        return CONTEXT_WINDOW_EXCEEDED
    if isinstance(error, str) and error.strip().lower() == _LM_STUDIO:
        return CONTEXT_WINDOW_EXCEEDED
    return None
