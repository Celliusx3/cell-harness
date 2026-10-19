"""The approvals: which tools need the person's approval, and which ones they approved always."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class NotApproved(LookupError):
    """A tool the person has not approved always, so there is nothing to revoke."""


class ApprovalsFile(BaseModel):
    """The approvals file: every tool the person has approved always."""

    model_config = ConfigDict(frozen=True)

    tools: tuple[str, ...] = ()


class Approvals:
    """The tools that need approval, and the approvals file that remembers which no longer do."""

    def __init__(
        self,
        configured_tools: frozenset[str],
        writing_tool_names: Callable[[], frozenset[str]],
        grants_path: Path,
    ) -> None:
        self._configured_tools = configured_tools
        self._writing_tool_names = writing_tool_names
        self._grants_path = grants_path

    @property
    def protected_tools(self) -> frozenset[str]:
        """The configured tools and the servers' tools that may write; each asks unless approved."""
        return self._configured_tools | self._writing_tool_names()

    def needs_approval(self, name: str) -> bool:
        """Whether a call to `name` must wait for the person."""
        return name in self.protected_tools and name not in self.approved_tools()

    def approved_tools(self) -> frozenset[str]:
        """What the approvals file holds right now; a missing file is empty."""
        if not self._grants_path.exists():
            return frozenset()
        raw = json.loads(self._grants_path.read_text(encoding="utf-8"))
        return frozenset(ApprovalsFile.model_validate(raw).tools)

    def grant(self, name: str) -> None:
        """Remember that `name` may run without asking."""
        if name not in self.protected_tools:
            raise ValueError(f"{name!r} is not a tool that asks for approval")
        self._write_grants(self.approved_tools() | {name})

    def revoke(self, name: str) -> None:
        """Make `name` ask again."""
        approved = self.approved_tools()
        if name not in approved:
            raise NotApproved(f"{name!r} is not approved")
        self._write_grants(approved - {name})

    def _write_grants(self, tools: frozenset[str]) -> None:
        self._grants_path.parent.mkdir(parents=True, exist_ok=True)
        grants = ApprovalsFile(tools=tuple(sorted(tools)))
        handle, temp = tempfile.mkstemp(dir=self._grants_path.parent, suffix=".tmp")
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            file.write(grants.model_dump_json(indent=2))
        os.replace(temp, self._grants_path)
