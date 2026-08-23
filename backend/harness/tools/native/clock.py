"""`get_current_time` — the smallest real tool.

Exists to prove the path end to end: the model is offered a schema, asks for a
call, and the result comes back in a form it can use. It is also the tool the
phase-8 guardrail must *not* flag — repeated calls that keep succeeding are
normal, and only failing or demonstrably-unproductive repetition is a loop.

The clock is injected rather than read from `datetime.now()` directly, so a test
can assert an exact string instead of matching a pattern.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field

from harness.tools.definition import EXECUTION_ERROR, Failure, Ok, ToolDefinition, ToolOutcome
from harness.tools.progress import ToolProgressReporter

Now = Callable[[], datetime]


class ClockArgs(BaseModel):
    """Arguments for `get_current_time`."""

    timezone: str = Field(
        default="UTC",
        description="IANA timezone name, e.g. 'Asia/Singapore' or 'UTC'.",
    )


def clock_tool(now: Now = lambda: datetime.now(UTC)) -> ToolDefinition[ClockArgs]:
    async def execute(args: ClockArgs, progress: ToolProgressReporter) -> ToolOutcome:
        try:
            zone = ZoneInfo(args.timezone)
        except (ZoneInfoNotFoundError, ValueError) as err:
            # A bad timezone is the model's mistake to correct, not ours to
            # paper over: defaulting to UTC would answer confidently with the
            # wrong time.
            return Failure(EXECUTION_ERROR, f"unknown timezone {args.timezone!r}: {err}")
        return Ok(content=now().astimezone(zone).isoformat(timespec="seconds"))

    return ToolDefinition.from_model(
        name="get_current_time",
        description="Get the current date and time in a given timezone.",
        args_model=ClockArgs,
        execute=execute,
    )
