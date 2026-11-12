"""An RRULE's timing: what is accepted, and when its next occurrence falls."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from harness.schedules.timing import InvalidRrule, next_after, zone_of

NEW_YORK_DAILY = "DTSTART;TZID=America/New_York:20260301T090000\nRRULE:FREQ=DAILY"


def test_a_tzid_rule_keeps_local_wall_time_across_daylight_saving() -> None:
    before = next_after(NEW_YORK_DAILY, datetime(2026, 3, 7, tzinfo=UTC))
    after = next_after(NEW_YORK_DAILY, datetime(2026, 3, 8, tzinfo=UTC))
    later = next_after(NEW_YORK_DAILY, datetime(2026, 3, 8, 13, tzinfo=UTC))

    assert before == datetime(2026, 3, 7, 14, tzinfo=UTC)
    assert after == datetime(2026, 3, 8, 13, tzinfo=UTC)
    assert later == datetime(2026, 3, 9, 13, tzinfo=UTC)
    new_york = ZoneInfo("America/New_York")
    assert [t.astimezone(new_york).hour for t in (before, after, later)] == [9, 9, 9]


def test_the_next_occurrence_is_strictly_after_the_instant_and_in_utc() -> None:
    rule = "DTSTART:20261112T080000Z\nRRULE:FREQ=HOURLY"

    following = next_after(rule, datetime(2026, 11, 12, 8, tzinfo=UTC))

    assert following == datetime(2026, 11, 12, 9, tzinfo=UTC)
    assert following is not None and following.tzinfo == UTC


def test_a_rule_with_nothing_left_has_no_next_occurrence() -> None:
    rule = "DTSTART:20260101T000000Z\nRRULE:FREQ=DAILY;COUNT=1"

    assert next_after(rule, datetime(2026, 11, 12, tzinfo=UTC)) is None


def test_the_zone_of_a_rule_is_its_tzid_or_utc() -> None:
    assert zone_of(NEW_YORK_DAILY) == ZoneInfo("America/New_York")
    assert zone_of("DTSTART:20261112T080000Z\nRRULE:FREQ=DAILY") == ZoneInfo("UTC")


@pytest.mark.parametrize(
    "rule",
    [
        "RRULE:FREQ=DAILY",
        "DTSTART:20261112T080000Z",
        "DTSTART:20261112T080000Z\nRRULE:FREQ=DAILY\nRRULE:FREQ=WEEKLY",
        "RRULE:FREQ=DAILY\nDTSTART:20261112T080000Z",
        "DTSTART:20261112T080000Z\nRRULE:FREQ=SECONDLY",
        "DTSTART:20261112T080000Z\nRRULE:FREQ=MINUTELY;BYSECOND=1,2",
        "DTSTART:20261112T080000Z\nRRULE:FREQ=DAILY;COUNT=1001",
        "DTSTART:20261112T080000Z\nRRULE:FREQ=DAILY;COUNT=0",
        "DTSTART:20261112T080000Z\nRRULE:FREQ=DAILY;COUNT=many",
        "DTSTART:20261112T080000Z\nRRULE:FREQ=DAILY;COUNT=2;UNTIL=20261201T000000Z",
        "DTSTART;TZID=Mars/Olympus:20261112T080000\nRRULE:FREQ=DAILY",
        "DTSTART:20261112T080000\nRRULE:FREQ=DAILY",
        "DTSTART;TZID=Asia/Singapore:20261112T080000Z\nRRULE:FREQ=DAILY",
        "DTSTART:20261112T080000Z\nRRULE:FREQ=FORTNIGHTLY",
        "DTSTART;TZID=Asia/Singapore:20261112T080000\nRRULE:FREQ=DAILY;UNTIL=20261201T000000",
    ],
)
def test_a_rule_outside_the_bounds_is_a_typed_error(rule: str) -> None:
    with pytest.raises(InvalidRrule) as raised:
        next_after(rule, datetime(2026, 11, 12, tzinfo=UTC))

    assert raised.value.reason
