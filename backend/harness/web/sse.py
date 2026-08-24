"""Server-sent-event framing for a conversation's log.

Two frame names, and the split between them is the whole protocol:

    event: session    one `SessionEvent`, verbatim
    event: end        the stream is over; do not reconnect

**Why `end` exists when the response also closes.** A clean ending and a dropped
connection look identical to a client reading a body — and they call for opposite
reactions. Seeing `end`, a client stops. Seeing the body end without it, a client
reconnects at its cursor. Without the frame, a browser suspended by a sleeping
laptop would either give up on a live turn or poll one that finished.

**`end` carries no reason.** How the turn ended is the `reason` on its `turn/end`,
which the client has already received as a `session` frame. A second copy here
would be a second answer to one question.

**No keepalive yet.** A comment frame every N seconds is what stops an idle
connection being dropped by a proxy or a dozing OS, and it needs a timeout race
against the subscription to emit. Nothing in this phase is silent long enough to
need it: the only tool is a clock, and a streaming reply arrives continuously. It
belongs with phase 5's first genuinely slow MCP tool, where a turn really does
spend minutes inside one call saying nothing.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from harness.runs.store import Run
from harness.runs.subscribe import subscribe
from harness.session.log import Session

MEDIA_TYPE = "text/event-stream"


def frame(event: str, data: str) -> str:
    """One SSE frame. `data` must already be a single line — JSON always is."""
    return f"event: {event}\ndata: {data}\n\n"


async def sse_frames(run: Run | None, session: Session, *, after: int) -> AsyncIterator[str]:
    """The conversation's events from `after`, then `end`.

    Two sources, one stream. A running turn is followed live through `subscribe`;
    an idle one serves the stored tail.

    **The idle branch is not an optimization — it closes a gap.** A turn that
    settles between a client's snapshot and its subscribe leaves events the client
    can never ask for again: its cursor says `n`, the log holds `n + 5`, and
    replying with a bare `end` would confirm it is up to date. Serving
    `events[after:]` makes the handoff correct no matter how the timing falls, and
    means a client never has to check "is anything running?" before subscribing.

    Deliberately **not** wrapped in `aclosing` by its caller, and it needs no
    protection of its own: a browser hanging up closes this generator, which
    closes the subscription, which owns nothing. The run is untouched — see
    `runs/__init__.py`.
    """
    if run is not None:
        async for event in subscribe(run, after=after):
            yield frame("session", event.model_dump_json())
    else:
        for event in session.events()[after:]:
            yield frame("session", event.model_dump_json())
    yield frame("end", "{}")
