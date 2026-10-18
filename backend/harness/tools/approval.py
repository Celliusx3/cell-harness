"""The approval gate: which tools ask the person first, and who has said "always"."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class StandingGrants(BaseModel):
    """The grants file: every tool the person has allowed always."""

    model_config = ConfigDict(frozen=True)

    tools: tuple[str, ...] = ()


class ApprovalGate:
    """The tools that ask, and the file that remembers which of them no longer ask."""

    def __init__(
        self,
        configured: frozenset[str],
        writing_tool_names: Callable[[], frozenset[str]],
        grants_path: Path,
    ) -> None:
        self._configured = configured
        self._writing_tool_names = writing_tool_names
        self._grants_path = grants_path

    @property
    def tools(self) -> frozenset[str]:
        """The configured tools and the servers' tools that may write; each asks unless granted."""
        return self._configured | self._writing_tool_names()

    def asks(self, name: str) -> bool:
        """Whether a call to `name` must wait for the person."""
        return name in self.tools and name not in self.granted()

    def granted(self) -> frozenset[str]:
        """What the grants file holds right now; a missing file is empty."""
        if not self._grants_path.exists():
            return frozenset()
        raw = json.loads(self._grants_path.read_text(encoding="utf-8"))
        return frozenset(StandingGrants.model_validate(raw).tools)

    def grant(self, name: str) -> None:
        """Remember that `name` may run without asking."""
        if name not in self.tools:
            raise ValueError(f"{name!r} is not a tool that asks for approval")
        self._write(self.granted() | {name})

    def revoke(self, name: str) -> None:
        """Make `name` ask again."""
        granted = self.granted()
        if name not in granted:
            raise KeyError(name)
        self._write(granted - {name})

    def _write(self, tools: frozenset[str]) -> None:
        self._grants_path.parent.mkdir(parents=True, exist_ok=True)
        grants = StandingGrants(tools=tuple(sorted(tools)))
        handle, temp = tempfile.mkstemp(dir=self._grants_path.parent, suffix=".tmp")
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            file.write(grants.model_dump_json(indent=2))
        os.replace(temp, self._grants_path)
