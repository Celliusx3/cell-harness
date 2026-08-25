"""Channels — ways in and out other than the browser.

    transport.py    `Channel` — the one Protocol a platform implements
    gateway.py      **one** gateway: inbound -> a run, the log -> outbound, and
                    supervision of every channel's background task
    commands.py     `/new` and `/stop`, shared by every text platform
    repository.py   the storage port for per-chat state
    repositories/   one file per backend — `jsonl.py` today
    telegram/       the first platform: `TelegramChannel`, and its command syntax

**Why a messenger is where the run store pays off.** On Telegram there is no
connection to outlive, because there never was one: a message arrives over a poll
or a webhook, and the reply goes out over the API minutes later. A design that
tied a turn to the connection that asked for it would have nowhere to put the
answer.

**One conversation at a time, and a queue behind it.** A browser can grey out its
composer; a phone cannot stop someone typing. So a message arriving mid-turn is
held and answered next — never refused, never merged into the running turn.
Folding a correction into a turn already in flight is `steer`, and doing it
honestly needs a durable inbox; that is a later phase.

Prior art, and it disagrees usefully. `hermes-agent` makes busy-behaviour a
three-way policy (`queue` | `steer` | `interrupt`) and defaults **text to queue**;
`duta-ilmu`, a production Telegram/WhatsApp platform, enforces per-conversation
FIFO by construction; cell-bot's browser answer — refuse with a `409` — is right
for a UI that can show the refusal and useless on a phone.

## Dedupe by consequence, not by default

Platforms **do** redeliver. Telegram warns outright that "updates may be received
twice" when polling restarts, and a webhook retries until it gets a `200`. There
is deliberately no guard against it here, and the rule is worth stating because
the instinct is to add one.

`hermes-agent` is the evidence. Five thousand lines of Telegram platform, and it
dedupes exactly **one** operation — `/restart` — for a reason its comment gives
plainly: a redelivered `/restart` restarts the gateway, which redelivers it, which
restarts the gateway. *"Ignoring the stale redelivery prevents a
self-perpetuating restart loop."* Ordinary messages are not guarded at all.

So the question is never "could this arrive twice?" but **"what does the second
one do?"**:

    ordinary message   answers twice          annoying
    /new               clears a cleared id    no-op
    /stop              "Nothing is running."  no-op

Nothing here compounds, loops, or destroys, so nothing here is guarded — and a
blanket guard was tried and removed. The one we had keyed on a *batch's* last
message id, and batch boundaries shift on redelivery, so it missed precisely when
it was needed. A half-working guarantee is worse than an honest absence.

**Add a guard when an operation earns one** — something that spends money without
a human present, deletes, or restarts the process — and guard *that operation*,
not the transport.

## Adding a platform

Everything between "a message arrived" and "a reply is ready" is already shared,
so a new platform is two small objects and one block of wiring:

1. **One class implementing `Channel`** — `run()`, `send_message()`,
   `send_typing()`, and a `channel` name. It owns its own limits, the way
   `TelegramChannel` owns the 4096-character split and the decision to send
   plain text rather than risk MarkdownV2 rejecting a whole message.
   `send_typing` is a no-op where the platform has no such idea, and `run()` is
   the part that genuinely differs — Telegram long-polls, WhatsApp serves a
   webhook, Discord holds a websocket. A redelivery is answered again rather
   than guarded; see "dedupe by consequence" above before adding a guard.
2. **One line in `build_channels`** (`web/server.py`) —
   `gateway.register(YourChannel(token, gateway))`. Registering both teaches the
   gateway how to reply and hands it the task to supervise. That function is the
   only place that knows which platforms exist.

Nothing in `gateway.py`, `commands.py` or `repository.py` should need to change,
and `tests/unit/test_channel_seam.py` holds a 20-line `FakeDiscord` that proves
it. If a third platform *does* force a change there, that is the signal the seam
is in the wrong place — worth fixing rather than working around, since the whole
point is that each platform costs less than the one before.
"""
