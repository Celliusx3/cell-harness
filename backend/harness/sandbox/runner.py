"""The sandbox seam."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

Bridge = Callable[[str, dict], Awaitable[object]]


class BridgeError(Exception):
    """Raised by a bridge to make the script's call throw."""


@dataclass(frozen=True)
class Script:
    """What one execution produced."""

    result: object = None
    logs: tuple[str, ...] = ()
    error: str | None = None


class Runner(ABC):
    """Runs one untrusted script."""

    @abstractmethod
    async def run(self, code: str, *, names: Sequence[str], bridge: Bridge) -> Script:
        """Run `code`, resolving every name it calls through `bridge`."""
        ...
