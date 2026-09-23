"""The files a skill brought with it, and the one way one is handed over."""

from __future__ import annotations

from harness.skills.models import SKILL_FILE, Skill

MAX_RESOURCE_BYTES = 64 * 1024
_LIST_DEPTH = 3


class UnreadableFile(ValueError):
    """The path names nothing this skill may hand over."""


def listing(skill: Skill) -> tuple[str, ...]:
    """Every file bundled beside the `SKILL.md`, as sorted relative posix paths."""
    found: list[str] = []
    for file in sorted(skill.dir.rglob("*")):
        relative = file.relative_to(skill.dir)
        if len(relative.parts) > _LIST_DEPTH or any(p.startswith(".") for p in relative.parts):
            continue
        if file.is_file() and relative.as_posix() != SKILL_FILE:
            found.append(relative.as_posix())
    return tuple(found)


def read(skill: Skill, path: str) -> str:
    """The text of one bundled file, confined to the skill's directory."""
    base = skill.dir.resolve()
    target = (skill.dir / path).resolve()
    if not target.is_relative_to(base) or target == base:
        raise UnreadableFile(f"{path!r} is not inside skill {skill.name!r}")
    if not target.is_file():
        raise UnreadableFile(f"skill {skill.name!r} has no file {path!r}")
    if target.stat().st_size > MAX_RESOURCE_BYTES:
        raise UnreadableFile(
            f"{path!r} is larger than {MAX_RESOURCE_BYTES // 1024} KiB and cannot be loaded whole"
        )
    try:
        return target.read_text(encoding="utf-8")
    except UnicodeDecodeError as err:
        raise UnreadableFile(f"{path!r} is not a text file") from err
    except OSError as err:
        raise UnreadableFile(f"{path!r} could not be read: {err}") from err
