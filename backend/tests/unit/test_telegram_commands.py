"""Recognising a command the way Telegram delivers one."""

from __future__ import annotations

import pytest

from harness.channels.commands import Command
from harness.channels.telegram.commands import parse


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("/new", Command.NEW),
        ("/stop", Command.STOP),
        ("/skills", Command.SKILLS),
        ("  /new  ", Command.NEW),
        ("/NEW", Command.NEW),
    ],
)
def test_a_slash_word_is_its_command(text, expected) -> None:
    assert parse(text) == expected


def test_the_botname_suffix_is_stripped() -> None:
    assert parse("/new@my_harness_bot") is Command.NEW


def test_any_other_slash_word_is_left_for_the_gateway() -> None:
    assert parse("/summarise this") is None
    assert parse("/find-place https://x") is None


@pytest.mark.parametrize("text", ["hello", "what is 1/2?", "", "   "])
def test_ordinary_text_is_not_a_command(text) -> None:
    assert parse(text) is None


def test_arguments_after_the_command_are_ignored() -> None:
    assert parse("/new please") is Command.NEW
