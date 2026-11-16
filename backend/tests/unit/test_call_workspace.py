"""A call carries the workspace of the chat it is made for, which a worker shares with its bot."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from harness.runtime.service import Runtime
from harness.tools import Ok, ToolContext, ToolOutcome
from tests.unit.fakes import EchoArgs, SteppedClient, calls_tool, completed, echo_tool
from tests.unit.helpers import drain, new_session, runtime_over
from tests.webapp import files_in


def recording_runtime(seen: list[Path | None]) -> Runtime:
    async def execute(args: EchoArgs, context: ToolContext) -> ToolOutcome:
        seen.append(context.origin.workspace)
        return Ok(content=args.value)

    client = SteppedClient(calls_tool("echo", '{"value": "42"}'), completed("ok"))
    return runtime_over(client, replace(echo_tool(), execute=execute))


async def test_a_call_carries_its_chats_workspace_when_the_runtime_keeps_files(tmp_path) -> None:
    seen: list[Path | None] = []
    for runtime_files in (files_in(tmp_path), None):
        runtime = replace(recording_runtime(seen), files=runtime_files)
        await drain(runtime.run("q", session=new_session("c0"), bot_id="notion"))

    assert seen == [files_in(tmp_path).workspace("c0"), None]


async def test_a_workers_call_carries_its_bots_workspace_not_its_own_logs(tmp_path) -> None:
    seen: list[Path | None] = []
    worker = replace(
        recording_runtime(seen),
        files=files_in(tmp_path),
        chat_id_for=lambda _session, bot_id: bot_id,
    )

    await drain(worker.run("q", session=new_session("ticket-1"), bot_id="translator"))

    assert seen == [files_in(tmp_path).workspace("translator")]
