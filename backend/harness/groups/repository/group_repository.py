"""Where the groups are kept: every group read in stored order, and a new one added after them."""

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
