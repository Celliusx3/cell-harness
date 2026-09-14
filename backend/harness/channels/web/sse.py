"""Server-sent-event framing for a conversation's log.

Two frame names, and the split between them is the whole protocol:

    event: session    one `SessionEvent`, verbatim
    event: end        the conversation is idle; do not reconnect

**Why `end` exists when the response also closes.** A clean ending and a dropped
connection look identical to a client reading a body — and they call for opposite
reactions. Seeing `end`, a client stops. Seeing the body end without it, a client
reconnects at its cursor. Without the frame, a browser suspended by a sleeping
laptop would either give up on a live turn or poll one that finished.

**`end` means the conversation is idle, not that a run settled.** A message sent
mid-turn is queued and becomes a *new* run the moment the old one settles. A
stream that said `end` on settling told the client "nothing more is coming"
precisely as the next turn started — the browser parked on it and the queued
message was invisible until a refresh. So the stream follows the conversation:
run settles, wait for the gateway's drain, and if that started a turn, keep
going at the same cursor.

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

from collections.abc import AsyncIterator, Awaitable, Callable

from harness.runs.store import Run
from harness.runs.subscribe import subscribe
from harness.session.log import Session

MEDIA_TYPE = "text/event-stream"

# What a stream reads from: a turn in flight, or the log as stored.
Source = Run | Session

# Answers "what is there to read now?" once the gateway has drained: the run a
# queued message just started, or the stored log — which may already hold that
# turn whole, if it finished before anyone looked.
AfterDrain = Callable[[], Awaitable[Source]]


def frame(event: str, data: str) -> str:
    """One SSE frame. `data` must already be a single line — JSON always is."""
    return f"event: {event}\ndata: {data}\n\n"


async def sse_frames(source: Source, *, after: int, after_drain: AfterDrain) -> AsyncIterator[str]:
    """The conversation's events from `after`, across every turn, then `end`.

    Two kinds of source, one cursor. A running turn is followed live through
    `subscribe`; a stored log serves its tail. Either way, once a source is
    exhausted `after_drain` says what is there now, and the stream continues
    from the same cursor — a run, or a log with more past the cursor than this
    stream has sent. That works because a run is flushed before it settles: the
    next source already holds every event this one delivered. It stops when the
    log has nothing past the cursor, which is what "idle" means here.

    **The stored tail is not an optimization — it closes a gap.** A turn that
    settles between a client's snapshot and its subscribe leaves events the client
    can never ask for again: its cursor says `n`, the log holds `n + 5`, and
    replying with a bare `end` would confirm it is up to date. The same gap opens
    after a drain — a queued turn short enough to finish before the stream looks
    is on disk and nowhere else — and serving `events[cursor:]` closes both.
    Going through `after_drain` even from a stored tail is deliberate too: a
    client reconnecting in the window between settle and drain would otherwise
    park on the same bug from a different door.

    Deliberately **not** wrapped in `aclosing` by its caller, and it needs no
    protection of its own: a browser hanging up closes this generator, which
    closes the subscription, which owns nothing. The run is untouched — see
    `runs/__init__.py`.
    """
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
