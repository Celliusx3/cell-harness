"""The error describer: an exception group unwinds to one line an operator can act on."""

from __future__ import annotations

from harness.mcp import McpConnectionError, McpNotConnectedError, McpTimeoutError
from harness.mcp._connection import describe_error


def test_a_one_member_group_comes_back_as_its_member_message() -> None:
    group = ExceptionGroup("connect failed", [McpConnectionError("server died")])

    assert describe_error(group) == "server died"


def test_a_group_nested_in_a_one_member_group_comes_back_as_the_innermost_message() -> None:
    group = ExceptionGroup("outer", [ExceptionGroup("inner", [McpNotConnectedError("no session")])])

    assert describe_error(group) == "no session"


def test_a_group_with_several_members_is_not_unwound() -> None:
    group = ExceptionGroup("two failures", [McpTimeoutError("first"), McpTimeoutError("second")])

    flattened = describe_error(group)

    assert flattened != "first"
    assert flattened != "second"


def test_an_error_with_an_empty_message_comes_back_as_its_type_name() -> None:
    assert describe_error(McpConnectionError()) == "McpConnectionError"


def test_a_plain_error_comes_back_as_its_own_message() -> None:
    assert describe_error(McpTimeoutError("server never answered")) == "server never answered"


def test_whitespace_around_the_message_is_stripped() -> None:
    assert describe_error(McpConnectionError("  server died \n")) == "server died"
