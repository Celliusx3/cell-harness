"""The browser's channel."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter

from harness.bots import BotService
from harness.channels.gateway import ChannelGateway
from harness.channels.web.routes import build_router
from harness.runs.service import RunService
from harness.session.service import SessionService

CHANNEL = "web"


class WebChannel:
    """HTTP in, the session log out."""

    channel = CHANNEL

    def __init__(
        self,
        sessions: SessionService,
        runs: RunService,
        gateway: ChannelGateway,
        bots: BotService,
    ) -> None:
        self.sessions = sessions
        self.runs = runs
        self.gateway = gateway
        self.bots = bots
        self.router: APIRouter = build_router(self)

    def conversation_for(self, chat_id: str) -> str:
        """A browser chat is named by the conversation it writes into."""
        return chat_id

    async def run(self) -> None:
        """Wait until cancelled."""
        await asyncio.Event().wait()
