"""The sandbox seam.

`Runner` is what code mode depends on. Concrete runtimes live beside this file
and nothing outside the package imports one — swapping Deno for a V8 isolate or
QuickJS is a change in the composition root.

An ABC rather than a `Protocol` for the reason `llm/client.py` gives: one method,
and every implementation is ours to change. The tests' fake runner is the second
implementation today, and subclassing is what stops it drifting from the real one
while its tests keep passing.

Deliberately knows nothing about tools. `tests/unit/test_layering.py` enforces it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

# What a name in the script resolves to. Plain values in, a plain value out: this
# package never learns what a tool is, which is what lets anything else use it.
Bridge = Callable[[str, dict], Awaitable[object]]


class BridgeError(Exception):
    """Raised by a bridge to make the script's call throw.

    The inversion happens here rather than in the script: callers may represent
    failure however they like, and every language a sandbox might run expects an
    exception.
    """


@dataclass(frozen=True)
class Script:
    """What one execution produced. A value, not an exception: a script that threw
    is ordinary traffic the caller recovers from."""

    result: object = None
    logs: tuple[str, ...] = ()
    error: str | None = None


class Runner(ABC):
    """Runs one untrusted script."""

    @abstractmethod
    async def run(self, code: str, *, names: Sequence[str], bridge: Bridge) -> Script:
        """Run `code`, resolving every name it calls through `bridge`.

        Implementations owe three things: the script reaches nothing the bridge
        did not give it, a `BridgeError` becomes a throw the script can catch,
        and the run is bounded — a script that never finishes is killed, not
        awaited.
        """
        ...
