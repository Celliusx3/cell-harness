"""`get_current_time` — the smallest real tool."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from harness.tools.definition import ToolDefinition
from harness.tools.models.context import ToolContext
from harness.tools.models.outcome import EXECUTION_ERROR, Failure, Ok, ToolOutcome
from harness.tools.native.clock.models import ClockArgs

Now = Callable[[], datetime]

GET_CURRENT_TIME = "get_current_time"


def clock_tool(now: Now = lambda: datetime.now(UTC)) -> ToolDefinition[ClockArgs]:
    async def execute(args: ClockArgs, _context: ToolContext) -> ToolOutcome:
        try:
            zone = ZoneInfo(args.timezone)
        except (ZoneInfoNotFoundError, ValueError) as err:
            return Failure(EXECUTION_ERROR, f"unknown timezone {args.timezone!r}: {err}")
        return Ok(content=now().astimezone(zone).isoformat(timespec="seconds"))

    return ToolDefinition.from_model(
        name=GET_CURRENT_TIME,
        description="Get the current date and time in a given timezone.",
        args_model=ClockArgs,
        execute=execute,
    )
