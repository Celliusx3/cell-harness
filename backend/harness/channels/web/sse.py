"""Server-sent-event framing for a conversation's log."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable

from harness.runs.store import Run
from harness.runs.subscribe import subscribe
from harness.session.log import Session

MEDIA_TYPE = "text/event-stream"

Source = Run | Session

AfterDrain = Callable[[], Awaitable[Source]]


def frame(event: str, data: str) -> str:
    """One SSE frame. `data` must already be a single line — JSON always is."""
    return f"event: {event}\ndata: {data}\n\n"


async def sse_frames(source: Source, *, after: int, after_drain: AfterDrain) -> AsyncIterator[str]:
    """The conversation's events from `after`, across every turn, then `end`."""
    cursor = after
    while True:
        if isinstance(source, Run):
            async for event in subscribe(source, after=cursor):
                cursor += 1
                yield frame("session", event.model_dump_json())
        else:
            for event in source.events()[cursor:]:
                cursor += 1
                yield frame("session", event.model_dump_json())
        source = await after_drain()
        if isinstance(source, Session) and len(source.events()) <= cursor:
            break
    yield frame("end", "{}")
