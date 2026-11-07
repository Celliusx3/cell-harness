"""What runs the PC: the Engine interface every engine implements."""

from __future__ import annotations

from typing import Protocol

from computer.models.command import CommandResult
from computer.models.pc import PcSpec, PcState, Program


class Engine(Protocol):
    """The PC's lifecycle and the programs run in it; failing to reach it is an EngineError."""

    @property
    def host_address(self) -> str:
        """The Mac's address as a program in the PC reaches it."""

    async def create(self, spec: PcSpec) -> None:
        """Make the PC and start it."""

    async def start(self, name: str) -> None: ...

    async def stop(self, name: str) -> None: ...

    async def remove(self, name: str) -> None:
        """Remove the PC, running or not; its home volume stays."""

    async def state(self, name: str) -> PcState: ...

    async def replacement_reason(self, spec: PcSpec) -> str | None:
        """Why the PC lacks the spec's ports, folders or (microsandbox) network rules, or None."""

    async def host_port(self, name: str, guest_port: int) -> int:
        """The loopback port on the Mac that `guest_port` is published on."""

    async def environment(self, name: str) -> dict[str, str]:
        """The variables the PC was made with."""

    async def run(
        self, name: str, program: Program, *, stdin: str | None, timeout_seconds: float
    ) -> CommandResult:
        """Run `program` to its end; None attaches no stdin. A non-zero exit is returned."""

    async def launch(self, name: str, program: Program) -> CommandResult:
        """Start `program` detached; the result is the launch's, not the program's."""
