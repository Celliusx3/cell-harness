"""How a running tool reports partway."""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Protocol


class ToolProgressReporter(Protocol):
    """What a tool calls to say how far along it is."""

    def __call__(self, *, percent: float | None, message: str | None) -> Awaitable[None]: ...
