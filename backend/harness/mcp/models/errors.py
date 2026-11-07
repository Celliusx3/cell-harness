"""What can go wrong talking to an MCP server."""

from __future__ import annotations


class McpConnectionError(RuntimeError):
    """The server could not be reached, or died."""


class McpTimeoutError(RuntimeError):
    """The server accepted the command and never answered."""


class McpNotConnectedError(RuntimeError):
    """There is no live session to carry this command."""


class RequiredServerError(RuntimeError):
    """A server the config marks `required` did not connect, so the app must not serve."""


class McpServerTaken(ValueError):
    """The id is already a built-in server's, or another saved server's."""


class McpServerNotFound(LookupError):
    """No server has this id."""


class McpServerBuiltIn(ValueError):
    """The server comes from config, so the screen cannot change or remove it."""
