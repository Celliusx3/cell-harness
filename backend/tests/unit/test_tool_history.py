"""A tool call's model history, the chat's session since its last clear, and its own workspace."""

from __future__ import annotations

from dataclasses import replace

from harness.session.domain.log import Session
from harness.tools import CallOrigin, Ok, Tool, ToolContext, ToolOutcome
from tests.unit.fakes import EchoArgs, SteppedClient, calls_tool, completed, echo_tool
from tests.unit.helpers import drain, new_session, runtime_over
from tests.webapp import files_in


def recording(seen: list[CallOrigin]) -> Tool[EchoArgs]:
    async def execute(args: EchoArgs, context: ToolContext) -> ToolOutcome:
        seen.append(context.origin)
        return Ok(content=args.value)

    return replace(echo_tool(), execute=execute)


async def test_a_cleared_chat_s_tools_run_in_a_new_model_history() -> None:
    seen: list[CallOrigin] = []
    client = SteppedClient(calls_tool("echo", '{"value": "42"}'), completed("ok"))
    fresh = new_session("c0")
    cleared = Session(fresh.header.model_copy(update={"numbered_from": 7}))

    await drain(runtime_over(client, recording(seen)).run("q", session=cleared, bot_id="notion"))

    assert [origin.history_id for origin in seen] == ["c0@7"]


async def test_a_group_call_carries_the_bot_s_own_workspace_as_its_turn_was_told(
    tmp_path,
) -> None:
    seen: list[CallOrigin] = []
    files = files_in(tmp_path)
    client = SteppedClient(calls_tool("echo", '{"value": "42"}'), completed("ok"))
    runtime = replace(
        runtime_over(client, recording(seen)), files=files, own_chat_of=lambda bot_id: bot_id
    )

    await drain(runtime.run("q", session=new_session("group-1"), bot_id="writer"))

    assert [(o.workspace, o.own_workspace) for o in seen] == [
        (files.workspace("group-1"), files.workspace("writer"))
    ]


async def test_in_its_own_chat_a_call_has_no_second_workspace(tmp_path) -> None:
    seen: list[CallOrigin] = []
    client = SteppedClient(calls_tool("echo", '{"value": "42"}'), completed("ok"))
    runtime = replace(
        runtime_over(client, recording(seen)),
        files=files_in(tmp_path),
        own_chat_of=lambda bot_id: bot_id,
    )

    await drain(runtime.run("q", session=new_session("writer"), bot_id="writer"))

    assert [o.own_workspace for o in seen] == [None]
