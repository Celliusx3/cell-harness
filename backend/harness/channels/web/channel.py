"""The browser's channel."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter

from harness.bots import BotService
from harness.channels.gateway import ChannelGateway
from harness.channels.web.routes import build_router
from harness.files import ChatFileService

CHANNEL = "web"


class WebChannel:
    """HTTP in, the session log out."""

    channel = CHANNEL

    def __init__(
        self,
        gateway: ChannelGateway,
        bots: BotService,
        files: ChatFileService,
    ) -> None:
        self.sessions = gateway.sessions
        self.runs = gateway.runs
        self.gateway = gateway
        self.bots = bots
        self.files = files
        self.router: APIRouter = build_router(self)

    def conversation_for(self, chat_id: str) -> str:
        """A browser chat is named by the conversation it writes into."""
        return chat_id

    async def run(self) -> None:
        """Wait until cancelled."""
        await asyncio.Event().wait()
