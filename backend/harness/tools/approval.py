"""The approval gate: which tools ask the person first, and who has said "always"."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

DENIED = "DENIED"
DENIED_RESULT = (
    "the user pressed Deny, so this call did not run and nothing changed. This is their "
    "decision, not a fault: do not retry it or work around it. Tell them you did not do it "
    "because they denied it."
)

Scope = Literal["once", "conversation", "always"]


class Approved(BaseModel):
    """The person let the call run, for this call, this conversation, or always."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["approved"] = "approved"
    scope: Scope


class Denied(BaseModel):
    """The person refused the call."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["denied"] = "denied"


Decision = Approved | Denied

_DECISION = TypeAdapter(Annotated[Decision, Field(discriminator="kind")])


def parse_decision(raw: object) -> Decision:
    """A posted body as the person's decision; `ValidationError` when it is not one."""
    return _DECISION.validate_python(raw)


class StandingGrants(BaseModel):
    """The grants file: every tool the person has allowed always."""

    model_config = ConfigDict(frozen=True)

    tools: tuple[str, ...] = ()


class ApprovalGate:
    """The listed tools, and the file that remembers which of them no longer ask."""

    def __init__(self, tools: frozenset[str], grants_path: Path) -> None:
        self._tools = tools
        self._grants_path = grants_path

    @property
    def tools(self) -> frozenset[str]:
        """Every tool that asks unless granted."""
        return self._tools

    def asks(self, name: str) -> bool:
        """Whether a call to `name` must wait for the person."""
        return name in self._tools and name not in self.granted()

    def granted(self) -> frozenset[str]:
        """What the grants file holds right now; a missing file is empty."""
        if not self._grants_path.exists():
            return frozenset()
        raw = json.loads(self._grants_path.read_text(encoding="utf-8"))
        return frozenset(StandingGrants.model_validate(raw).tools)

    def grant(self, name: str) -> None:
        """Remember that `name` may run without asking."""
        if name not in self._tools:
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
