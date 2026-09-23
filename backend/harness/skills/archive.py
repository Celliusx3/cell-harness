"""A zipped skill folder: what its entries claim, and what may be written from them."""

from __future__ import annotations

import zipfile
from collections.abc import Sequence
from pathlib import PurePosixPath
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict

from harness.skills.models import SKILL_FILE, InvalidSkill, valid_name

MAX_ARCHIVE_BYTES = 5 * 1024 * 1024
MAX_UNPACKED_BYTES = 30 * 1024 * 1024
MAX_FILES = 200

JUNK_DIRS = ("__MACOSX", "__pycache__")
_FORMAT_MASK = 0o170000
_LINK_MODE = 0o120000


class Member(NamedTuple):
    """One entry as the archive describes it, before anything is extracted."""

    name: str
    size: int
    is_dir: bool
    is_link: bool


class PlannedFile(NamedTuple):
    """An entry to read, and where it goes relative to the skill directory."""

    member: str
    path: PurePosixPath


class ArchivePlan(BaseModel):
    """The one skill an archive may become, and every file to write under it."""

    model_config = ConfigDict(frozen=True)

    name: str
    files: tuple[PlannedFile, ...]


def members_of(zipped: zipfile.ZipFile) -> tuple[Member, ...]:
    """Every entry the archive lists, with the mode bits that say what it is."""
    return tuple(
        Member(
            name=info.filename,
            size=info.file_size,
            is_dir=info.is_dir(),
            is_link=(info.external_attr >> 16) & _FORMAT_MASK == _LINK_MODE,
        )
        for info in zipped.infolist()
    )


def plan(members: Sequence[Member]) -> ArchivePlan:
    """Where every member goes under one skill directory, or `InvalidSkill` saying why not."""
    for member in members:
        _refuse_unsafe(member)
    kept = [member for member in members if not member.is_dir and not _ignored(member.name)]
    name = _sole_top_level(kept)
    if not valid_name(name):
        raise InvalidSkill(
            f"folder {name!r} is not a skill name: lowercase letters, digits and single "
            "hyphens, at most 64"
        )
    files = tuple(
        PlannedFile(member=member.name, path=PurePosixPath(member.name).relative_to(name))
        for member in kept
    )
    if not any(planned.path == PurePosixPath(SKILL_FILE) for planned in files):
        raise InvalidSkill(f"the archive has no {name}/{SKILL_FILE}")
    unpacked = sum(member.size for member in kept)
    if unpacked > MAX_UNPACKED_BYTES:
        raise InvalidSkill(
            f"the archive unpacks to {unpacked} bytes, larger than the {MAX_UNPACKED_BYTES} allowed"
        )
    if len(files) > MAX_FILES:
        raise InvalidSkill(
            f"the archive holds {len(files)} files, more than the {MAX_FILES} allowed"
        )
    return ArchivePlan(name=name, files=files)


def _refuse_unsafe(member: Member) -> None:
    path = PurePosixPath(member.name)
    if path.is_absolute() or ".." in path.parts or "\\" in member.name:
        raise InvalidSkill(f"entry {member.name!r} would escape the skill directory")
    if member.is_link:
        raise InvalidSkill(f"entry {member.name!r} is a link, which is never installed")


def _ignored(name: str) -> bool:
    parts = PurePosixPath(name).parts
    return not parts or any(part in JUNK_DIRS or part.startswith(".") for part in parts)


def _sole_top_level(kept: Sequence[Member]) -> str:
    tops = {PurePosixPath(member.name).parts[0] for member in kept}
    loose = [member for member in kept if len(PurePosixPath(member.name).parts) == 1]
    if len(tops) != 1 or loose:
        raise InvalidSkill(
            "the archive must hold exactly one top-level folder and nothing beside it"
        )
    return tops.pop()
