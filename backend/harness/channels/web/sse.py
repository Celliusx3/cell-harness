"""Server-sent-event framing for a conversation's log."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import suppress

from harness.runs.store import Run
from harness.runs.subscribe import subscribe
from harness.session.log import Numbered, Session

MEDIA_TYPE = "text/event-stream"

KEEP_ALIVE = ": keep-alive\n\n"

KEEP_ALIVE_SECONDS = 15.0

Source = Run | Session

AfterDrain = Callable[[], Awaitable[Source]]


def frame(event: str, data: str) -> str:
    """One SSE frame. `data` must already be a single line — JSON always is."""
    return f"event: {event}\ndata: {data}\n\n"


def session_frame(item: Numbered) -> str:
    """One logged event as an SSE frame whose `id` is the event's number."""
    return f"event: session\nid: {item.number}\ndata: {item.event.model_dump_json()}\n\n"


async def sse_frames(source: Source, *, after: int, after_drain: AfterDrain) -> AsyncGenerator[str]:
    """The conversation's events from `after`, across every turn, then `end`."""
    cursor = after
    while True:
        if isinstance(source, Run):
            async for item in subscribe(source, after=cursor):
                yield session_frame(item)
            cursor = source.session.next_number()
        else:
            for item in source.numbered_events_from(cursor):
                yield session_frame(item)
            cursor = source.next_number()
        source = await after_drain()
        if isinstance(source, Session) and source.next_number() <= cursor:
            break
    yield frame("end", "{}")


async def kept_alive(frames: AsyncGenerator[str]) -> AsyncGenerator[str]:
    """`frames` as they arrive, and `KEEP_ALIVE` whenever `KEEP_ALIVE_SECONDS` pass without one."""
    pending = asyncio.ensure_future(anext(frames))
    try:
        while True:
            await asyncio.wait({pending}, timeout=KEEP_ALIVE_SECONDS)
            if not pending.done():
                yield KEEP_ALIVE
                continue
            try:
                item = pending.result()
            except StopAsyncIteration:
                return
            yield item
            pending = asyncio.ensure_future(anext(frames))
    finally:
        if pending.cancel():
            with suppress(asyncio.CancelledError):
                await pending
        await frames.aclose()
