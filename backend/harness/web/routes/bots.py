"""The bots: list them, make one, edit one, delete one."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Response, status

from harness.bots import Bot, BotDraft, BotNotFound, BotPermanent, BotStore

logger = logging.getLogger(__name__)


def build_router(bots: BotStore) -> APIRouter:
    """Every bot, and the changes a person can make to them."""
    router = APIRouter(prefix="/api/bots", tags=["bots"])

    @router.get("", response_model=list[Bot])
    async def list_bots() -> list[Bot]:
        return list(await bots.list())

    @router.post("", status_code=status.HTTP_201_CREATED, response_model=Bot)
    async def create_bot(body: BotDraft) -> Bot:
        bot = await bots.create(body.name, body.instructions)
        logger.info("bot %s created", bot.id)
        return bot

    @router.put("/{bot_id}", response_model=Bot)
    async def update_bot(bot_id: str, body: BotDraft) -> Bot:
        try:
            return bots.update(bot_id, body.name, body.instructions)
        except BotNotFound as err:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from err

    @router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_bot(bot_id: str) -> Response:
        try:
            bots.delete(bot_id)
        except BotPermanent as err:
            raise HTTPException(status.HTTP_409_CONFLICT, detail=str(err)) from err
        except BotNotFound as err:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from err
        logger.info("bot %s deleted", bot_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
