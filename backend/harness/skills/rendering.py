"""How a skill reads to the model — the same string whether it asked for it
through the `skill` tool or a person typed `/name`."""

from __future__ import annotations

from pathlib import Path

from harness.skills.catalog import read_body
from harness.skills.models import SKILL_FILE, Skill

# Bundled files are *listed* with the body so the model knows what it may ask
# for. Capped, with the count of the rest, so a skill shipping a directory of
# fixtures does not cost more than its instructions.
MAX_LISTED_FILES = 20
_LIST_DEPTH = 3


def instructions(skill: Skill) -> str:
    """The skill as the model receives it: the body in a `<skill>` tag, then
    what else the directory holds. Read from disk now, not when the catalog was
    built. Shared with `/name` invocation so a skill looks the same to the
    model whether it asked for it or a person did.
    """
    parts = [f'<skill name="{skill.name}">\n{read_body(skill)}\n</skill>']
    listed, more = _bundled(skill.dir)
    if listed:
        files = ", ".join(listed) + (f", and {more} more" if more else "")
        parts.append(f"Bundled files, readable with `path`: {files}")
    return "\n\n".join(parts)


def _bundled(root: Path) -> tuple[list[str], int]:
    """Every file under the skill directory except `SKILL.md`, as relative
    posix paths; the first `MAX_LISTED_FILES` and how many were left out."""
    found: list[str] = []
    for file in sorted(root.rglob("*")):
        relative = file.relative_to(root)
        if len(relative.parts) > _LIST_DEPTH or any(p.startswith(".") for p in relative.parts):
            continue
        if file.is_file() and relative.as_posix() != SKILL_FILE:
            found.append(relative.as_posix())
    return found[:MAX_LISTED_FILES], max(0, len(found) - MAX_LISTED_FILES)
