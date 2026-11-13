"""The bots: list, make, edit, archive, restore or delete one, and choose its keys."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Response, status

from harness.bots import Bot, BotDraft, BotEdit, BotService
from harness.bots.router.schemas import AllowedSecrets
from harness.runs.service.run_service import RunService
from harness.schedules import ScheduleService
from harness.secrets import SecretName, SecretNotFound, SecretService

logger = logging.getLogger(__name__)


def _refuse_an_unsaved_model(secrets: SecretService, name: SecretName | None) -> None:
    """Raise a 422 when `name` is not a saved LLM credential; `None` is no model, and passes."""
    reason = None if name is None else secrets.not_a_model_reason(name)
    if reason is not None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=reason)


def _edit_routes(router: APIRouter, bots: BotService, secrets: SecretService) -> None:
    """Listing, making and editing bots, and choosing the keys each may use."""

    @router.get("", response_model=list[Bot])
    async def list_bots() -> list[Bot]:
        return list(await bots.active_bots())

    @router.get("/archived", response_model=list[Bot])
    async def list_archived_bots() -> list[Bot]:
        return list(bots.archived_bots())

    @router.post("", status_code=status.HTTP_201_CREATED, response_model=Bot)
    async def create_bot(body: BotDraft) -> Bot:
        _refuse_an_unsaved_model(secrets, body.model)
        bot = await bots.create(body)
        logger.info("bot %s created", bot.id)
        return bot

    @router.put("/{bot_id}", response_model=Bot)
    async def update_bot(bot_id: str, body: BotEdit) -> Bot:
        _refuse_an_unsaved_model(secrets, body.model)
        bot = bots.update(bot_id, body)
        logger.info("bot %s saved, answering on %s", bot_id, bot.model_credential)
        return bot

    @router.put("/{bot_id}/secrets", response_model=Bot)
    async def set_bot_secrets(bot_id: str, body: AllowedSecrets) -> Bot:
        saved = {summary.name for summary in secrets.summaries()}
        unsaved = next((name for name in body.names if name not in saved), None)
        if unsaved is not None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(SecretNotFound(unsaved)))
        bot = bots.set_allowed_secrets(bot_id, body.names)
        logger.info("bot %s may use %s", bot_id, list(bot.secret_names))
        return bot


def _archive_routes(
    router: APIRouter, bots: BotService, runs: RunService, schedules: ScheduleService
) -> None:
    """Archiving, restoring and deleting a bot; archiving or deleting one stops its turn."""

    async def stop_speaking(bot_id: str) -> None:
        """End the bot's own chat's turn, and the discussion of any group it is speaking in."""
        for chat_id in {bots.chat_of(bot_id), *runs.chats_spoken_in(bot_id)}:
            await runs.stop(chat_id)

    @router.post("/{bot_id}/archive", status_code=status.HTTP_204_NO_CONTENT)
    async def archive_bot(bot_id: str) -> Response:
        bots.archive(bot_id)
        await stop_speaking(bot_id)
        logger.info("bot %s archived", bot_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post("/{bot_id}/restore", status_code=status.HTTP_204_NO_CONTENT)
    async def restore_bot(bot_id: str) -> Response:
        bots.restore(bot_id)
        logger.info("bot %s restored", bot_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_bot(bot_id: str) -> Response:
        bots.archive(bot_id)
        await stop_speaking(bot_id)
        await bots.delete(bot_id)
        schedules.delete_of_bot(bot_id)
        logger.info("bot %s, its chat and its schedules deleted", bot_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)


def build_router(
    bots: BotService, runs: RunService, secrets: SecretService, schedules: ScheduleService
) -> APIRouter:
    """Every bot, and the changes a person can make; archiving or deleting one stops its turn."""
    router = APIRouter(prefix="/api/bots", tags=["bots"])
    _edit_routes(router, bots, secrets)
    _archive_routes(router, bots, runs, schedules)
    return router
