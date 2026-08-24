"""The HTTP surface — the first one, and the reason phases 1–3 shipped none.

    schemas.py              request and response bodies, typed
    sse.py                  framing for the event stream
    routes/conversations.py the endpoints
    server.py               `create_app` — the composition root for the server

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
