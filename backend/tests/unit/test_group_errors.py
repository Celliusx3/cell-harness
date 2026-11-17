"""What a refused group change tells the person."""

from __future__ import annotations

from harness.groups import EmptyGroupError, NotAChatMemberError


def test_an_empty_group_names_the_group() -> None:
    assert str(EmptyGroupError("g1")) == "every member of group 'g1' is archived or deleted"


def test_a_bot_outside_the_chat_names_the_bot_and_the_chat() -> None:
    assert str(NotAChatMemberError("c1", "b1")) == "bot 'b1' is no active member of chat 'c1'"
