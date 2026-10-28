"""A bot's page asks for a code that links a Telegram or Discord direct chat to that bot."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from harness.bots import BotNotFound, BotService
from harness.channels.links import LINK_CODE_SECONDS, LinkCodes
from harness.secrets import SecretService
from harness.secrets.models.details import ChatPlatform

logger = logging.getLogger(__name__)


class LinkCodeRequest(BaseModel):
    """The platform whose direct chat the code is for."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    platform: ChatPlatform


class IssuedLinkCode(BaseModel):
    """A code, the seconds it lasts, and the name of the bot it links to."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    expires_in_seconds: int
    bot_name: str


def build_router(codes: LinkCodes, bots: BotService, keyring: SecretService) -> APIRouter:
    """A link code for an active bot, on a platform whose token is saved, from any device."""
    router = APIRouter(prefix="/api/bots", tags=["link codes"])

    @router.post(
        "/{bot_id}/link-codes", status_code=status.HTTP_201_CREATED, response_model=IssuedLinkCode
    )
    async def issue_link_code(bot_id: str, body: LinkCodeRequest) -> IssuedLinkCode:
        try:
            bot = bots.active_bot(bot_id)
        except BotNotFound as err:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from err
        if await asyncio.to_thread(keyring.chat_platform_token, body.platform) is None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail=_no_token(body.platform))
        issued = codes.issue(bot.id, body.platform)
        logger.info("a %s link code issued for bot %s", body.platform, bot.id)
        return IssuedLinkCode(
            code=issued.code, expires_in_seconds=LINK_CODE_SECONDS, bot_name=bot.name
        )

    return router


def _no_token(platform: ChatPlatform) -> str:
    """Why a code is refused for a platform whose token is not saved, and what to do."""
    name = platform.capitalize()
    return f"{name} has no token yet. Add the {name} token on the Credentials page first."
