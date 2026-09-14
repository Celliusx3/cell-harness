"""The browser's channel.

A peer of `TelegramChannel`, and the same bargain: one object owns one platform's
wire. Telegram's wire is a poll loop and `sendMessage`; this one's is an
`APIRouter`.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter

from harness.channels.gateway import ChannelGateway
from harness.channels.protocol import OnMissing
from harness.channels.web.routes import build_router
from harness.runs.store import RunStore
from harness.session.service import SessionService

CHANNEL = "web"


class WebChannel:
    """HTTP in, the session log out.

    **No `send_message`.** It is not omitted for lack of time — a browser has no
    address to send to. It comes and reads, holding a `GET` open and following the
    log through `subscribe()`. So this class does not satisfy `Pushing`, and the
    gateway never spawns a delivery worker for it. See `channels/web/__init__.py`
    for what `hermes-agent` did instead and what it cost them.

    **`on_missing = "raise"`.** A browser client names the conversation it wants,
    so an id that matches nothing is a mistake to report, not an instruction to
    create something. Telegram is the opposite: a chat whose conversation vanished
    must recover, because the person holding the phone cannot fix it.
    """

    channel = CHANNEL
    on_missing: OnMissing = "raise"

    def __init__(
        self,
        sessions: SessionService,
        runs: RunStore,
        gateway: ChannelGateway,
    ) -> None:
        self.sessions = sessions
        self.runs = runs
        self.gateway = gateway
        # Built here, so the routes close over this object instead of reaching
        # into `app.state`. The same reason `TelegramChannel` holds its own PTB
        # `Application`: what a channel needs to work is the channel's to carry.
        self.router: APIRouter = build_router(self)

    async def run(self) -> None:
        """Wait until cancelled.

        Not a stub. The contract is "receive until cancelled", and this channel
        does receive — through uvicorn serving `self.router`, rather than a loop it
        drives itself. There is genuinely nothing to poll, so it waits, and the
        gateway supervises it like any other channel.
        """
        await asyncio.Event().wait()
