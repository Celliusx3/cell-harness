"""How a running tool reports partway.

Separate from `definition` because `agent/loop.py` needs the type to build a
reporter and `tools/definition.py` needs it to type an executor — one importing
the other would make a cycle.

`percent` is `None` when the total is not knowable, which is the common case (a
download that never sent Content-Length, a query with no row count). `None` is
not zero: a progress bar should show indeterminate, not "no progress".
"""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Protocol


class ToolProgressReporter(Protocol):
    """What a tool calls to say how far along it is.

    Keyword-only, so a call site reads as prose and a tool reporting only a
    message does not have to pass a positional `None` for the percentage.
    """

    def __call__(self, *, percent: float | None, message: str | None) -> Awaitable[None]: ...
