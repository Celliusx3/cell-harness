"""What can go wrong talking to an MCP server."""

from __future__ import annotations


class McpConnectionError(RuntimeError):
    """The server could not be reached, or died."""


class McpTimeoutError(RuntimeError):
    """The server accepted the command and never answered."""


class McpNotConnectedError(RuntimeError):
    """There is no live session to carry this command."""


def describe(error: BaseException) -> str:
    """A one-line cause an operator can act on."""
    while isinstance(error, BaseExceptionGroup) and len(error.exceptions) == 1:
        error = error.exceptions[0]
    message = str(error).strip()
    return message or type(error).__name__
