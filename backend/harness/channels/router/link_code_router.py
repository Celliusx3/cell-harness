"""A bot's page asks for a code that links a Telegram or Discord direct chat to that bot."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, status

from harness.bots import BotNotFound, BotService
from harness.channels.router.link_code_schemas import IssuedLinkCode, LinkCodeRequest
from harness.channels.service.links import LINK_CODE_SECONDS, LinkCodes
from harness.secrets import SecretService
from harness.secrets.domain.details import ChatPlatform

logger = logging.getLogger(__name__)


class LinkCodeRouter:
    """A link code for an active bot, on a platform whose token is saved, from any device."""

    def __init__(self, codes: LinkCodes, bots: BotService, keyring: SecretService) -> None:
        self._codes = codes
        self._bots = bots
        self._keyring = keyring
        self.router: APIRouter = APIRouter(prefix="/api/bots", tags=["link codes"])
        self.router.add_api_route(
            "/{bot_id}/link-codes",
            self.issue_link_code,
            methods=["POST"],
            status_code=status.HTTP_201_CREATED,
            response_model=IssuedLinkCode,
        )

    async def issue_link_code(self, bot_id: str, body: LinkCodeRequest) -> IssuedLinkCode:
        try:
            bot = self._bots.active_bot(bot_id)
        except BotNotFound as err:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from err
        if await asyncio.to_thread(self._keyring.chat_platform_token, body.platform) is None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail=_no_token(body.platform))
        issued = self._codes.issue(bot.id, body.platform)
        logger.info("a %s link code issued for bot %s", body.platform, bot.id)
        return IssuedLinkCode(
            code=issued.code, expires_in_seconds=LINK_CODE_SECONDS, bot_name=bot.name
        )


def _no_token(platform: ChatPlatform) -> str:
    """Why a code is refused for a platform whose token is not saved, and what to do."""
    name = platform.capitalize()
    return f"{name} has no token yet. Add the {name} token on the Credentials page first."
