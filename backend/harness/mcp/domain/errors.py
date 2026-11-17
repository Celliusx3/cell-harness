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


class NotAnAppPage(ValueError):
    """The resource an app asked for is not a `ui://` page of the MCP Apps type."""


class AppToolNotFound(LookupError):
    """The app's server publishes no tool by that name."""


class AppToolRefused(PermissionError):
    """The tool is not one this app may call: hidden from apps, or bound to another app."""


def describe_error(error: BaseException) -> str:
    """A one-line cause an operator can act on."""
    while isinstance(error, BaseExceptionGroup) and len(error.exceptions) == 1:
        error = error.exceptions[0]
    message = str(error).strip()
    return message or type(error).__name__
