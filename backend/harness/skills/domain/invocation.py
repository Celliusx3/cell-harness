"""`/name args` — a person loads a skill, so the model does not have to decide."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from harness.skills.domain.models import is_skill_name

SKILL_TAG_OPEN = '<skill name="'
MARKER = "\n\n" + SKILL_TAG_OPEN


class TypedInvocation(BaseModel):
    """The short form of an invoked message: which skill, and what was typed."""

    model_config = ConfigDict(frozen=True)

    skill: str
    typed: str


def invoked_skill_name(text: str) -> str | None:
    """The skill name a message starts with, or `None` for ordinary text."""
    first, _, _ = text.lstrip().partition(" ")
    first = first.split("\n", 1)[0]
    if not first.startswith("/"):
        return None
    name = first[1:]
    return name if is_skill_name(name) else None


def typed_invocation(content: str) -> TypedInvocation | None:
    """The typed line and skill name from an expanded message, or `None`."""
    typed, marker, rest = content.partition(MARKER)
    if not marker:
        return None
    skill, quote, _ = rest.partition('"')
    if not quote or not is_skill_name(skill):
        return None
    return TypedInvocation(skill=skill, typed=typed)
