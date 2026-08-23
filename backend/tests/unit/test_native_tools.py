"""The shipped native tools."""

from __future__ import annotations

from datetime import UTC, datetime

from harness.tools.definition import EXECUTION_ERROR, Failure, Ok
from harness.tools.native.clock import clock_tool
from tests.unit.helpers import no_progress

FIXED = datetime(2026, 8, 23, 12, 30, 0, tzinfo=UTC)


def frozen_clock():
    return clock_tool(now=lambda: FIXED)


async def test_defaults_to_utc() -> None:
    outcome = await frozen_clock().invoke("{}", progress=no_progress)

    assert outcome == Ok(content="2026-08-23T12:30:00+00:00")


async def test_converts_to_a_named_timezone() -> None:
    outcome = await frozen_clock().invoke('{"timezone": "Asia/Singapore"}', progress=no_progress)

    assert outcome == Ok(content="2026-08-23T20:30:00+08:00")


async def test_an_unknown_timezone_is_a_failure_not_a_silent_utc() -> None:
    """Defaulting would answer confidently with the wrong time — the one outcome
    worse than admitting the timezone is unknown."""
    outcome = await frozen_clock().invoke('{"timezone": "Mars/Olympus"}', progress=no_progress)

    assert isinstance(outcome, Failure)
    assert outcome.code == EXECUTION_ERROR
    assert "Mars/Olympus" in outcome.message


def test_the_schema_documents_its_one_argument() -> None:
    schema = frozen_clock().spec().input_schema

    assert "IANA" in schema["properties"]["timezone"]["description"]
    # Optional: a caller that just wants "now" should not have to name a zone.
    assert "timezone" not in schema.get("required", [])
