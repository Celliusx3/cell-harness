"""`ticket_report`: a worker's report in a fixed form, heard by its bot when the turn ends."""

from __future__ import annotations

from harness.tools.models.context import ToolContext
from harness.tools.models.outcome import INVALID_ARGUMENTS, Failure, Ok, ToolOutcome
from harness.tools.models.tool import Tool
from harness.tools.native.tickets.models import TicketReportArgs

TICKET_REPORT = "ticket_report"

ASKING_STATES = frozenset({"blocked", "waiting"})

_DESCRIPTION = (
    "Report this ticket's state to the orchestrator, then end your turn. The states ready, "
    "blocked, failed, dropped and waiting are what the orchestrator hears when your turn ends; "
    "the last one you report wins. The state progress only records a step and tells nobody. "
    "The orchestrator passes question to the user unchanged."
)


def ticket_report_tool() -> Tool[TicketReportArgs]:
    """The tool a worker reports with; the report is read back from the worker's own log."""

    async def execute(args: TicketReportArgs, context: ToolContext) -> ToolOutcome:
        if args.question is not None and args.state not in ASKING_STATES:
            return Failure(
                INVALID_ARGUMENTS,
                f"a question goes only with the state blocked or waiting, not {args.state}",
            )
        if args.state == "progress":
            return Ok("Recorded.")
        return Ok("Reported. End your turn now.")

    return Tool.from_model(
        name=TICKET_REPORT, description=_DESCRIPTION, args_model=TicketReportArgs, execute=execute
    )
