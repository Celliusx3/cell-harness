"""Run per-item work under a deadline, and return what finished.

The harness bounds one MCP call at 60 seconds (`mcp/store.py`
`COMMAND_TIMEOUT_SECONDS`), and it is a module constant — not configuration, so
this server cannot raise it. Worse, the harness serves one call per connection
at a time, so the model cannot get concurrency by issuing several calls.

That makes partial results the whole design rather than a nicety: reading five
reels at ~15s each does not fit, so the call does what it can inside a softer
budget and reports the rest as `timeout` for a cheap second call. Nothing already
done is thrown away.

`asyncio.timeout` alone would not do: it cancels the *group*, losing the finished
work along with the unfinished. This waits on each item individually against a
shared deadline instead.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence


async def with_budget[K, V](
    keys: Sequence[K],
    work: Callable[[K], Awaitable[V]],
    *,
    seconds: float,
    concurrency: int,
    on_timeout: Callable[[K], V],
) -> list[V]:
    """Run `work` over `keys`, bounded by `concurrency`, capped at `seconds`.

    Returns one value per key, in the caller's order. Keys whose work did not
    finish get `on_timeout(key)` — a real result describing what to do next,
    never an exception, because a raise here would take the finished siblings
    with it.
    """
    if not keys:
        return []

    limit = asyncio.Semaphore(concurrency)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + seconds

    async def guarded(key: K) -> V:
        async with limit:
            remaining = deadline - loop.time()
            if remaining <= 0:
                # Already out of budget before this item even started — the
                # common case for items 4 and 5 of a batch. Not an error.
                return on_timeout(key)
            async with asyncio.timeout(remaining):
                return await work(key)

    tasks = [asyncio.create_task(guarded(key)) for key in keys]
    settled = await asyncio.gather(*tasks, return_exceptions=True)

    out: list[V] = []
    for key, result in zip(keys, settled, strict=True):
        if isinstance(result, TimeoutError):
            out.append(on_timeout(key))
        elif isinstance(result, BaseException):
            # Cancellation is the one thing that must keep travelling: the caller
            # going away is not a per-item outcome to report.
            if isinstance(result, asyncio.CancelledError):
                raise result
            raise result
        else:
            out.append(result)
    return out
