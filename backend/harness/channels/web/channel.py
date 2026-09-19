"""The browser's channel."""

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
    """HTTP in, the session log out."""

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
        self.router: APIRouter = build_router(self)

    async def run(self) -> None:
        """Wait until cancelled."""
        await asyncio.Event().wait()
