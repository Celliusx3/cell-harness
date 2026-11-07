"""What can go wrong talking to an MCP server."""

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
