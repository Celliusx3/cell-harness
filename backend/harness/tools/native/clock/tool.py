"""`get_current_time` — the smallest real tool."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field

from harness.tools.context import ToolContext
from harness.tools.definition import EXECUTION_ERROR, Failure, Ok, ToolDefinition, ToolOutcome

Now = Callable[[], datetime]


class ClockArgs(BaseModel):
    """Arguments for `get_current_time`."""

    timezone: str = Field(
        default="UTC",
        description="IANA timezone name, e.g. 'Asia/Singapore' or 'UTC'.",
    )


CLOCK = "get_current_time"


def clock_tool(now: Now = lambda: datetime.now(UTC)) -> ToolDefinition[ClockArgs]:
    async def execute(args: ClockArgs, _context: ToolContext) -> ToolOutcome:
        try:
            zone = ZoneInfo(args.timezone)
        except (ZoneInfoNotFoundError, ValueError) as err:
            return Failure(EXECUTION_ERROR, f"unknown timezone {args.timezone!r}: {err}")
        return Ok(content=now().astimezone(zone).isoformat(timespec="seconds"))

    return ToolDefinition.from_model(
        name=CLOCK,
        description="Get the current date and time in a given timezone.",
        args_model=ClockArgs,
        execute=execute,
    )
