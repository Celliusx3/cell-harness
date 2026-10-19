"""Redacting a key out of text a site sent back."""

from __future__ import annotations

import base64
import json
from functools import reduce
from urllib.parse import quote

REDACTED_SECRET = "[secret]"


def redacted(text: str, value: str) -> str:
    """`text` with `value` replaced by `[secret]`: as is, JSON-escaped, URL-quoted and base64."""
    forms = {
        value,
        json.dumps(value)[1:-1],
        quote(value, safe=""),
        base64.b64encode(value.encode()).decode(),
    }
    longest_first = sorted(forms, key=len, reverse=True)
    return reduce(
        lambda redacting, form: redacting.replace(form, REDACTED_SECRET), longest_first, text
    )
