"""What runs the phone: the Engine interface every engine implements."""

from __future__ import annotations

from typing import Protocol

from phone.models.command import CommandResult
from phone.models.phone import PhoneSpec, PhoneState, Program


class Engine(Protocol):
    """The phone's lifecycle and the programs run in it; failing to reach it is an EngineError."""

    async def create(self, spec: PhoneSpec) -> None:
        """Make the phone and start it."""

    async def start(self, name: str) -> None: ...

    async def state(self, name: str) -> PhoneState: ...

    async def run(
        self, name: str, program: Program, *, stdin: str | None, timeout_seconds: float
    ) -> CommandResult:
        """Run `program` to its end; None attaches no stdin. A non-zero exit is returned."""

    async def launch(self, name: str, program: Program) -> CommandResult:
        """Start `program` detached; the result is the launch's, not the program's."""
