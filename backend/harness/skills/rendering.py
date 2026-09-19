"""How a skill reads to the model, from the `skill` tool or a typed `/name` alike."""

from __future__ import annotations

from pathlib import Path

from harness.skills.catalog import read_body
from harness.skills.invocation import SKILL_TAG_OPEN
from harness.skills.models import SKILL_FILE, Skill

MAX_LISTED_FILES = 20
_LIST_DEPTH = 3


def instructions(skill: Skill) -> str:
    """The skill as the model receives it: the body in a `<skill>` tag, then its files."""
    parts = [f'{SKILL_TAG_OPEN}{skill.name}">\n{read_body(skill)}\n</skill>']
    listed, more = _bundled(skill.dir)
    if listed:
        files = ", ".join(listed) + (f", and {more} more" if more else "")
        parts.append(f"Bundled files, readable with `path`: {files}")
    return "\n\n".join(parts)


def _bundled(root: Path) -> tuple[list[str], int]:
    """The first `MAX_LISTED_FILES` bundled files as relative paths, and how many were left out."""
    found: list[str] = []
    for file in sorted(root.rglob("*")):
        relative = file.relative_to(root)
        if len(relative.parts) > _LIST_DEPTH or any(p.startswith(".") for p in relative.parts):
            continue
        if file.is_file() and relative.as_posix() != SKILL_FILE:
            found.append(relative.as_posix())
    return found[:MAX_LISTED_FILES], max(0, len(found) - MAX_LISTED_FILES)
