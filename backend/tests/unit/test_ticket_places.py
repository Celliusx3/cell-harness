"""Who may run next, from a bot's places in use, its limit, the line, and whether it answers."""

from __future__ import annotations

import pytest

from harness.tickets.places import Occupancy, PlaceKind, freed, place_for, taken


@pytest.mark.parametrize(
    ("held", "limit", "first", "answer", "expected"),
    [
        (Occupancy(running=2), 3, True, False, "normal"),
        (Occupancy(running=2), 3, False, False, None),
        (Occupancy(running=3), 3, True, False, None),
        (Occupancy(running=2), 3, False, True, "normal"),
        (Occupancy(running=3), 3, False, True, "extra"),
        (Occupancy(running=3, extra_in_use=True), 3, False, True, None),
        (Occupancy(running=4), 2, True, False, None),
    ],
)
def test_a_turn_takes_a_free_place_in_line_and_an_answer_takes_the_extra_one(
    held: Occupancy, limit: int, first: bool, answer: bool, expected: PlaceKind | None
) -> None:
    assert place_for(held, limit, first_in_line=first, answer=answer) == expected


def test_a_place_taken_and_freed_leaves_the_count_as_it_was() -> None:
    held = Occupancy(running=1)

    assert freed(taken(held, "normal"), "normal") == held
    assert taken(held, "extra") == Occupancy(running=1, extra_in_use=True)
    assert freed(taken(held, "extra"), "extra") == held
