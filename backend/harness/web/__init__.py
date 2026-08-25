"""The composition root — what assembles a server, not what it serves.

    server.py   `create_app` and the builders behind it

The HTTP surface itself moved to `channels/web/`, because it is one channel's wire
in the same way `channels/telegram/` is Telegram's. What is left here is the part
that belongs to no channel: reading settings, building the store, the agent and the
gateway, and mounting whatever routers the channels bring.

**What the browser gets is `SessionEvent`s and a cursor**, from both the snapshot
and the stream. Not a bespoke API shape: a new event type becomes a new renderer
rather than a new endpoint, and a replayed conversation cannot drift from a live
one because there is only one thing being rendered.

We diverge from DeepSeek Harness here deliberately — they expose unary RPC at
`POST /api/<namespace>/<method>` plus two WebSocket downlinks. Their RPC shape
exists to serve compile-time TypeScript codegen we do not have, and their mux
socket exists because they have many concurrent stream types where we have one.
See DESIGN.md §7 for the full argument and the trigger to revisit.
"""
