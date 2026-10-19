"""A note-writing tool behind approvals, and a runtime that offers it — for the approval tests."""

from __future__ import annotations

from pathlib import Path

from harness.runtime.hooks import HookChain
from harness.runtime.service import Runtime
from harness.tools import Approvals, Ok, Tool, ToolOutcome, ToolService, Toolset
from tests.unit.fakes import EchoArgs

WRITE = "memory__write_note"


def approvals_asking_for(tmp_path: Path, *tools: str) -> Approvals:
    return Approvals(frozenset(tools), frozenset, tmp_path / "approvals.json")


def note_writer(ran: list[str]) -> Tool[EchoArgs]:
    async def execute(args: EchoArgs, _context) -> ToolOutcome:
        ran.append(args.value)
        return Ok(content=f"saved {args.value}")

    return Tool.from_model(
        name=WRITE, description="Save a note.", args_model=EchoArgs, execute=execute
    )


def runtime_offering(
    client, approvals: Approvals, *tools: Tool, hooks: HookChain | None = None
) -> Runtime:
    tool_service = ToolService(tools, approvals=approvals)
    toolset = Toolset(tool_service, default_tools=[t.name for t in tools])
    return Runtime(model="m", client=client, images=None, tools=toolset, hooks=hooks or HookChain())
