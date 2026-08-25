"""Recognising a command the way Telegram delivers one.

Separate from `test_channel_service.py` for the same reason the code is: these
assert a **Telegram convention**. A WhatsApp user typing `/new` has sent the
literal text `/new`, and asserting a leading slash there would be asserting a
rule that platform does not have.
"""

from __future__ import annotations

import pytest

from harness.channels.commands import Command
from harness.channels.telegram.commands import parse


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("/new", Command.NEW),
        ("/stop", Command.STOP),
        ("  /new  ", Command.NEW),
        ("/NEW", Command.NEW),
    ],
)
def test_a_slash_word_is_its_command(text, expected) -> None:
    assert parse(text) == expected


def test_the_botname_suffix_is_stripped() -> None:
    """Telegram appends `@botname` in groups. Without this the command silently
    becomes a prompt the moment the bot joins one."""
    assert parse("/new@my_harness_bot") is Command.NEW


def test_an_unknown_slash_word_is_a_command_not_a_prompt() -> None:
    """Someone typing `/summarise` meant a command; handing it to the model
    produces a confident answer to a question nobody asked."""
    assert parse("/summarise this") is Command.UNKNOWN


@pytest.mark.parametrize("text", ["hello", "what is 1/2?", "", "   "])
def test_ordinary_text_is_not_a_command(text) -> None:
    assert parse(text) is None


def test_arguments_after_the_command_are_ignored() -> None:
    """`/new please` is still `/new` — this phase's commands take none."""
    assert parse("/new please") is Command.NEW
