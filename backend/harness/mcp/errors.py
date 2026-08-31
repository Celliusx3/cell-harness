"""What can go wrong talking to an MCP server.

Distinct from the SDK's own `MCPError`: these are *our* vocabulary, and the tool
adapter maps each to a different `Failure` code so the model gets told whether a
tool is gone or merely broken.
"""

from __future__ import annotations


class McpConnectionError(RuntimeError):
    """The server could not be reached, or died."""


class McpTimeoutError(RuntimeError):
    """The server accepted the command and never answered."""


class McpNotConnectedError(RuntimeError):
    """There is no live session to carry this command."""


def describe(error: BaseException) -> str:
    """A one-line cause an operator can act on.

    Exceptions escaping `async with Client(...)` arrive wrapped in an
    `ExceptionGroup` — reporting that verbatim gives "unhandled errors in a
    TaskGroup (1 sub-exception)", which names nothing. Unwrap single-child
    groups until something real is left.
    """
    while isinstance(error, BaseExceptionGroup) and len(error.exceptions) == 1:
        error = error.exceptions[0]
    message = str(error).strip()
    return message or type(error).__name__
