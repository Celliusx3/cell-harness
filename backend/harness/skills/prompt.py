"""How a skill reads to the model, from the `skill` tool or a typed `/name` alike."""

from __future__ import annotations

from harness.skills.catalog import read_body
from harness.skills.invocation import SKILL_TAG_OPEN
from harness.skills.models import Skill
from harness.skills.resources import listing

MAX_LISTED_FILES = 20


def instructions(skill: Skill) -> str:
    """The skill as the model receives it: the body in a `<skill>` tag, then its files."""
    parts = [f'{SKILL_TAG_OPEN}{skill.name}">\n{read_body(skill)}\n</skill>']
    files = listing(skill)
    if files:
        more = len(files) - MAX_LISTED_FILES
        listed = ", ".join(files[:MAX_LISTED_FILES])
        parts.append(
            f"Bundled files, readable with `path`: {listed}"
            + (f", and {more} more" if more > 0 else "")
        )
    return "\n\n".join(parts)
