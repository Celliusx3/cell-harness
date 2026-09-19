"""`/name args` — a person loads a skill, so the model does not have to decide."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from harness.skills.models import valid_name

SKILL_TAG_OPEN = '<skill name="'
MARKER = "\n\n" + SKILL_TAG_OPEN


class Display(BaseModel):
    """The short form of an invoked message: which skill, and what was typed."""

    model_config = ConfigDict(frozen=True)

    skill: str
    typed: str


def parse(text: str) -> str | None:
    """The skill name a message starts with, or `None` for ordinary text."""
    first, _, _ = text.lstrip().partition(" ")
    first = first.split("\n", 1)[0]
    if not first.startswith("/"):
        return None
    name = first[1:]
    return name if valid_name(name) else None


def display(content: str) -> Display | None:
    """The typed line and skill name from an expanded message, or `None`."""
    typed, marker, rest = content.partition(MARKER)
    if not marker:
        return None
    skill, quote, _ = rest.partition('"')
    if not quote or not valid_name(skill):
        return None
    return Display(skill=skill, typed=typed)
