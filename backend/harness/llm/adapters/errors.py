"""Which provider errors the loop can do something about.

One today: the request was too big for the model's context. Providers say it in
different shapes — OpenAI, vLLM and ilmu's proxy set `error.code` to
`context_length_exceeded`; LM Studio answers `{"error": "Context length
exceeded"}`, a bare string. Both were observed on 2026-09-16; both are matched
exactly. Anything else is `None`: ilmu's chat models refuse an oversized
request with a generic `invalid_request`, and a classifier that read "invalid"
as "too long" would compact a conversation over a malformed tool schema.
"""

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
