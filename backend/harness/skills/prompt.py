"""How skills read to the model: the list of those it may load, and one loaded by name."""

from __future__ import annotations

from collections.abc import Sequence

from harness.prompts import SKILL_LIST_INTRO
from harness.skills.catalog import read_body
from harness.skills.invocation import SKILL_TAG_OPEN
from harness.skills.models import Skill
from harness.skills.resources import listing

MAX_LISTED_FILES = 20


def available_skills(skills: Sequence[Skill]) -> str:
    """The skills the model may load, named and described; empty when there are none."""
    if not skills:
        return ""
    lines = [SKILL_LIST_INTRO, "", *(f"- {s.name}: {s.description}" for s in skills)]
    return "\n".join(lines)


def instructions(skill: Skill, *, shipped: bool) -> str:
    """The skill as the model receives it: its body, its folder when shipped, its files."""
    parts = [f'{SKILL_TAG_OPEN}{skill.name}">\n{read_body(skill)}\n</skill>']
    if shipped:
        parts.append(f"This skill's folder: {skill.dir.resolve()}")
    files = listing(skill)
    if files:
        more = len(files) - MAX_LISTED_FILES
        listed = ", ".join(files[:MAX_LISTED_FILES])
        parts.append(
            f"Bundled files, readable with `path`: {listed}"
            + (f", and {more} more" if more > 0 else "")
        )
    return "\n\n".join(parts)
