"""When a schedule runs: one DTSTART line and one RRULE line, read by python-dateutil."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime, tzinfo
from typing import NamedTuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.rrule import rrule, rrulestr

MAX_RRULE_COUNT = 1000
UTC_ZONE = ZoneInfo("UTC")
_DTSTART_PATTERN = re.compile(r"DTSTART(?:;TZID=(?P<tzid>[^:;]+))?:\d{8}T\d{6}(?P<utc>Z?)")


class InvalidRrule(ValueError):
    """An rrule outside the bounds a schedule accepts, and the short reason why."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def next_after(text: str, instant: datetime) -> datetime | None:
    """The first occurrence of `text` strictly after `instant`, in UTC; `None` when none is left."""
    following = _rule(text).after(instant, inc=False)
    return None if following is None else following.astimezone(UTC)


def latest_at_or_before(text: str, instant: datetime) -> datetime | None:
    """The last occurrence of `text` at or before `instant`, in UTC; `None` when none is yet."""
    latest = _rule(text).before(instant, inc=True)
    return None if latest is None else latest.astimezone(UTC)


def zone_of(text: str) -> ZoneInfo:
    """The zone `text`'s DTSTART names; UTC when it ends in Z."""
    start, _ = _lines(text)
    tzid = _tzid(start)
    return UTC_ZONE if tzid is None else _zone(tzid)


def _rule(text: str) -> rrule:
    """`text` read as one rule, once it is inside the bounds."""
    start, recurrence = _lines(text)
    tzid = _tzid(start)
    _check_parts(_parts(recurrence))
    tzids: Mapping[str, tzinfo] = {} if tzid is None else {tzid: _zone(tzid)}
    try:
        parsed = rrulestr(text, tzids=tzids)
    except (ValueError, TypeError) as err:
        raise InvalidRrule(str(err)) from err
    if not isinstance(parsed, rrule):
        raise InvalidRrule("expected one DTSTART line and one RRULE line")
    return parsed


class RruleLines(NamedTuple):
    start: str
    recurrence: str


def _lines(text: str) -> RruleLines:
    lines = text.strip().splitlines()
    if len(lines) != 2 or not lines[0].startswith("DTSTART") or not lines[1].startswith("RRULE:"):
        raise InvalidRrule("expected one DTSTART line, a newline, and one RRULE line")
    return RruleLines(lines[0].strip(), lines[1].strip())


def _tzid(line: str) -> str | None:
    """The DTSTART line's TZID, `None` for Z; it must carry exactly one of the two."""
    matched = _DTSTART_PATTERN.fullmatch(line)
    if matched is None:
        raise InvalidRrule("DTSTART must be DTSTART:YYYYMMDDTHHMMSSZ or DTSTART;TZID=<zone>:...")
    if (matched["tzid"] is None) == (matched["utc"] == ""):
        raise InvalidRrule("DTSTART must end in Z or carry TZID, not both or neither")
    return matched["tzid"]


def _zone(tzid: str) -> ZoneInfo:
    try:
        return ZoneInfo(tzid)
    except (ZoneInfoNotFoundError, ValueError) as err:
        raise InvalidRrule(f"unknown time zone {tzid!r}") from err


def _parts(line: str) -> dict[str, str]:
    pairs = [part.partition("=") for part in line.removeprefix("RRULE:").split(";") if part]
    return {key.upper(): value for key, _, value in pairs}


def _check_parts(parts: Mapping[str, str]) -> None:
    if parts.get("FREQ", "").upper() == "SECONDLY":
        raise InvalidRrule("FREQ=SECONDLY is not allowed; a schedule runs at most once a minute")
    if len(parts.get("BYSECOND", "").split(",")) > 1:
        raise InvalidRrule("BYSECOND takes one value")
    if "COUNT" in parts and "UNTIL" in parts:
        raise InvalidRrule("COUNT and UNTIL cannot be combined")
    if "COUNT" in parts:
        _check_count(parts["COUNT"])


def _check_count(count: str) -> None:
    if not count.isdigit() or not 1 <= int(count) <= MAX_RRULE_COUNT:
        raise InvalidRrule(f"COUNT must be from 1 to {MAX_RRULE_COUNT}")
