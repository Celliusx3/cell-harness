"""The browser's channel — HTTP in, the session log out.

    channel.py   `WebChannel`, and the router it owns
    routes.py    the endpoints
    schemas.py   request and response bodies, typed
    sse.py       framing for the event stream

A peer of `channels/telegram/`, and the same shape: one object owns one platform's
wire. What differs is which way the reply travels. Telegram is **pushed** to —
`bot.send_message` is an outgoing call to somewhere. A browser is not somewhere; it
comes and reads, holding a `GET` open and following the session log through
`subscribe()`. So this channel implements no `send_message`, and the gateway never
asks it to send.

That absence is the design. `hermes-agent` made the opposite choice — its
`APIServerAdapter` satisfies the same interface as Telegram and stubs the method
that cannot work, `"API server uses HTTP request/response, not send()"`, returning
failure forever. Four other modules then special-case that platform back out. An
interface a member cannot honour is one that has to be worked around everywhere.
"""
