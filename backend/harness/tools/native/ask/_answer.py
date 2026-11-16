"""A model's reply read as JSON when it is JSON."""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, ConfigDict, JsonValue

JSON_FENCE = re.compile(r"```(?:json)?[ \t]*\n(.*?)\n?[ \t]*```", re.DOTALL)


class ParsedReply(BaseModel):
    """A reply's text as it is saved and shown, and its value: the JSON it holds, else the text."""

    model_config = ConfigDict(frozen=True)

    text: str
    value: JsonValue


def parsed_reply(reply: str) -> ParsedReply:
    """`reply` as JSON, a ```json fence around it removed, when it parses; else as text."""
    fenced = JSON_FENCE.fullmatch(reply.strip())
    body = fenced.group(1) if fenced else reply
    try:
        return ParsedReply(text=body, value=json.loads(body))
    except ValueError:
        return ParsedReply(text=reply, value=reply)
