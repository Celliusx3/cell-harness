"""A worker that asks the person runs nothing it listed after the question in that step."""

from __future__ import annotations

import json

from harness.llm import Completion, StreamEvent, ToolCall, ToolCallChunk
from harness.session.domain.models import ToolResultEvent
from harness.tools import BLOCKED, Ok, Tool, ToolContext, ToolOutcome
from harness.tools.native.tickets import TICKET_REPORT, ticket_report_tool
from tests.unit.fakes import EchoArgs, SteppedClient
from tests.unit.helpers import drain, new_session, runtime_over

ASKED = json.dumps(
    {"state": "blocked", "summary": "uv is not installed.", "question": "May I install uv?"}
)
REPORT = ToolCall(id="report", name=TICKET_REPORT, arguments=ASKED)
INSTALL = ToolCall(id="install", name="install", arguments='{"value": "uv"}')


def calls_in_one_step(*calls: ToolCall) -> list[StreamEvent]:
    return [
        *(ToolCallChunk(call=call) for call in calls),
        Completion(full_text="", tool_calls=calls),
    ]


def install_tool(installed: list[str]) -> Tool[EchoArgs]:
    async def execute(args: EchoArgs, context: ToolContext) -> ToolOutcome:
        installed.append(args.value)
        return Ok(content=f"installed {args.value}")

    return Tool.from_model(
        name="install", description="Install a program.", args_model=EchoArgs, execute=execute
    )


async def test_an_install_listed_after_the_question_does_not_run() -> None:
    installed: list[str] = []
    session = new_session()
    runtime = runtime_over(
        SteppedClient(calls_in_one_step(REPORT, INSTALL)),
        ticket_report_tool(),
        install_tool(installed),
    )

    await drain(runtime.run("go", session=session, bot_id="b"))

    (skipped,) = [
        e for e in session.events() if isinstance(e, ToolResultEvent) and e.error == BLOCKED
    ]
    assert installed == []
    assert skipped.message.tool_call_id == "install"
    assert TICKET_REPORT in skipped.message.content[0].text
