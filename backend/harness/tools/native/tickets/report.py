"""`ticket_report`: a worker's report in a fixed form, heard by its bot when the turn ends."""

from __future__ import annotations

from harness.tools.domain.context import ToolContext
from harness.tools.domain.outcome import INVALID_ARGUMENTS, Failure, Ok, ToolOutcome
from harness.tools.domain.tool import Tool
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
        mismatch = ask_mismatch(args)
        if mismatch is not None:
            return Failure(INVALID_ARGUMENTS, mismatch)
        if args.state == "progress":
            return Ok("Recorded.")
        return Ok("Reported. End your turn now.", ends_turn=True)

    return Tool.from_model(
        name=TICKET_REPORT, description=_DESCRIPTION, args_model=TicketReportArgs, execute=execute
    )


def ask_mismatch(args: TicketReportArgs) -> str | None:
    """Why `args` cannot be asked the way it says; `None` when the way fits the arguments."""
    if args.ask != "text" and args.question is None:
        return f"the ask {args.ask} goes only with a question"
    if (args.ask == "choice") != (args.options is not None):
        return "options go with the ask choice, and the ask choice needs options"
    secret = args.ask == "secret"
    if secret != (args.secret_name is not None) or secret != (args.secret_destination is not None):
        return "secret_name and secret_destination go with the ask secret, which needs both"
    return None
