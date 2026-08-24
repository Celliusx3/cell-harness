"""Runs — a turn that outlives the connection that asked for it.

**Ported from cell-bot's `app/conversations/runs.py`**, which DESIGN.md §1 marks
"Take" and the teardown calls its single most product-relevant piece. The store
owning the task, `subscribe(after)`, the condition guarding both facts, and
"a disconnect drops a subscription; cancel is the only thing that ends a run" are
all theirs. One thing is not, and it is called out below.

The reason this package exists, and the reason phases 1–3 shipped no HTTP: a chat
product's turns are long. A download, a transcription, a generated deck. Stream a
reply on the POST response and a closed tab kills four minutes of work.

So a turn runs as a **task the store owns**, and a client *subscribes*:

    store.py       `Run` and `RunStore` — start, stop, look up by conversation
    subscribe.py   read a run's events from a cursor, live

**A subscriber owns nothing.** It only reads. That is what makes "closing the SSE
response must not cancel the run" structurally true rather than a rule someone has
to remember — there is no ownership for a browser's hang-up to propagate through.

**There is no event buffer, and that is the one departure from cell-bot.** Theirs
keeps `run.events: list[AgentEvent]` alongside the session log — two lists, two
cursors, one for watching live and one for reloading history. Here a subscriber
reads the live `Session`'s log directly, because that log is already append-only
with its index as a stable cursor (`session/log.py`) and is already a superset of
what the loop yields.

One list, one cursor: `?after=4` means the same thing to a disk snapshot and to a
live stream, so the UI renders both through one code path and cannot drift between
them. dsh reaches the same primitive from the other side — `readFrom(id, fromSeq)`
in their `session-persistence`, a suffix read from a sequence number.
"""
