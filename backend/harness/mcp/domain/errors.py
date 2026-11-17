"""What can go wrong talking to an MCP server, and the one line that says why."""

from __future__ import annotations


class McpConnectionError(RuntimeError):
    """The server could not be reached, or died."""


class McpTimeoutError(RuntimeError):
    """The server accepted the command and never answered."""


class McpNotConnectedError(RuntimeError):
    """There is no live session to carry this command."""


class McpServerTaken(ValueError):
    """The id is already another saved server's."""


class McpServerNotFound(LookupError):
    """No server has this id."""


def describe_error(error: BaseException) -> str:
    """A one-line cause an operator can act on."""
    while isinstance(error, BaseExceptionGroup) and len(error.exceptions) == 1:
        error = error.exceptions[0]
    message = str(error).strip()
    return message or type(error).__name__
