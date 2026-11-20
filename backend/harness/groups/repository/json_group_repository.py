"""`groups.json`: its groups, read whole, added or replaced one at a time, the file rewritten."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from harness.groups.domain.models import Group, GroupsFile


class JsonGroupRepository:
    """The stored groups of one file; a missing file holds none."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def all(self) -> tuple[Group, ...]:
        """Every stored group, in stored order."""
        return self._read().groups

    def add(self, group: Group) -> None:
        """Store a new group after every stored group."""
        self._write(GroupsFile(groups=(*self._read().groups, group)))

    def update(self, group: Group) -> None:
        """Replace the stored group with `group`'s id, in its place."""
        stored = self._read().groups
        self._write(GroupsFile(groups=tuple(group if g.id == group.id else g for g in stored)))

    def _read(self) -> GroupsFile:
        if not self._path.exists():
            return GroupsFile()
        return GroupsFile.model_validate_json(self._path.read_text(encoding="utf-8"))

    def _write(self, stored: GroupsFile) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            file.write(stored.model_dump_json(indent=2))
        os.replace(temp, self._path)
