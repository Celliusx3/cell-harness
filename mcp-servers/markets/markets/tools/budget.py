"""Run per-item work under a deadline, and return what finished."""

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
    """Run `work` over `keys`, bounded by `concurrency`, capped at `seconds`."""
    if not keys:
        return []

    limit = asyncio.Semaphore(concurrency)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + seconds

    async def guarded(key: K) -> V:
        async with limit:
            remaining = deadline - loop.time()
            if remaining <= 0:
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
            raise result
        else:
            out.append(result)
    return out
