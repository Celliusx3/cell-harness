"""Where the groups are kept: every group read in stored order, one added after them or replaced."""

from __future__ import annotations

from typing import Protocol

from harness.groups.domain.models import Group


class GroupRepository(Protocol):
    """The stored groups, as storage."""

    def all(self) -> tuple[Group, ...]:
        """Every stored group, in stored order."""
        ...

    def add(self, group: Group) -> None:
        """Store a new group after every stored group."""
        ...

    def update(self, group: Group) -> None:
        """Replace the stored group with `group`'s id, in its place."""
        ...
