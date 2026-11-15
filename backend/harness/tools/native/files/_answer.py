"""A model's reply read as JSON when it is JSON, and what a script receives for it."""

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


class ImageAnswer(BaseModel):
    """What `ask_about_images` returns to a script: the answer, and where it was saved."""

    model_config = ConfigDict(frozen=True)

    answer: JsonValue
    saved_to: str | None


def parsed_reply(reply: str) -> ParsedReply:
    """`reply` as JSON, a ```json fence around it removed, when it parses; else as text."""
    fenced = JSON_FENCE.fullmatch(reply.strip())
    body = fenced.group(1) if fenced else reply
    try:
        return ParsedReply(text=body, value=json.loads(body))
    except ValueError:
        return ParsedReply(text=reply, value=reply)
