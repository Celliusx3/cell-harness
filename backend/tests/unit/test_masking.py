"""A key shows only its last four characters, and nothing when it is too short to hide."""

from __future__ import annotations

from harness.secrets.masking import last_four


def test_a_key_of_eight_or_more_shows_its_last_four_characters() -> None:
    assert last_four("abcd1234") == "1234"


def test_a_key_shorter_than_eight_shows_no_characters() -> None:
    assert last_four("abc1234") is None
