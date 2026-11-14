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


class BotRouter:
    """Every bot, and the changes a person can make; archiving or deleting one stops its turn."""

    def __init__(
        self, bots: BotService, runs: RunService, secrets: SecretService, schedules: ScheduleService
    ) -> None:
        self._bots = bots
        self._runs = runs
        self._secrets = secrets
        self._schedules = schedules
        self.router: APIRouter = APIRouter(prefix="/api/bots", tags=["bots"])
        self._add_edit_routes()
        self._add_archive_routes()

    def _add_edit_routes(self) -> None:
        """Listing, making and editing bots, and choosing the keys each may use."""
        self.router.add_api_route("", self.list_bots, methods=["GET"], response_model=list[Bot])
        self.router.add_api_route(
            "/archived", self.list_archived_bots, methods=["GET"], response_model=list[Bot]
        )
        self.router.add_api_route(
            "",
            self.create_bot,
            methods=["POST"],
            status_code=status.HTTP_201_CREATED,
            response_model=Bot,
        )
        self.router.add_api_route("/{bot_id}", self.update_bot, methods=["PUT"], response_model=Bot)
        self.router.add_api_route(
            "/{bot_id}/secrets", self.set_bot_secrets, methods=["PUT"], response_model=Bot
        )

    def _add_archive_routes(self) -> None:
        """Archiving, restoring and deleting a bot."""
        no_content = status.HTTP_204_NO_CONTENT
        self.router.add_api_route(
            "/{bot_id}/archive", self.archive_bot, methods=["POST"], status_code=no_content
        )
        self.router.add_api_route(
            "/{bot_id}/restore", self.restore_bot, methods=["POST"], status_code=no_content
        )
        self.router.add_api_route(
            "/{bot_id}", self.delete_bot, methods=["DELETE"], status_code=no_content
        )

    async def list_bots(self) -> list[Bot]:
        return list(await self._bots.open_active_bots())

    async def list_archived_bots(self) -> list[Bot]:
        return list(self._bots.archived_bots())

    async def create_bot(self, body: BotDraft) -> Bot:
        self._refuse_unsaved_model(body.model)
        bot = await self._bots.create(body)
        logger.info("bot %s created", bot.id)
        return bot

    async def update_bot(self, bot_id: str, body: BotEdit) -> Bot:
        self._refuse_unsaved_model(body.model)
        bot = self._bots.update(bot_id, body)
        logger.info("bot %s saved, answering on %s", bot_id, bot.model_credential)
        return bot

    async def set_bot_secrets(self, bot_id: str, body: AllowedSecrets) -> Bot:
        saved = {summary.name for summary in self._secrets.summaries()}
        unsaved = next((name for name in body.names if name not in saved), None)
        if unsaved is not None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(SecretNotFound(unsaved)))
        bot = self._bots.set_allowed_secrets(bot_id, body.names)
        logger.info("bot %s may use %s", bot_id, list(bot.secret_names))
        return bot

    async def archive_bot(self, bot_id: str) -> Response:
        self._bots.archive(bot_id)
        await self._stop_speaking(bot_id)
        logger.info("bot %s archived", bot_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def restore_bot(self, bot_id: str) -> Response:
        self._bots.restore(bot_id)
        logger.info("bot %s restored", bot_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def delete_bot(self, bot_id: str) -> Response:
        self._bots.archive(bot_id)
        await self._stop_speaking(bot_id)
        await self._bots.delete(bot_id)
        self._schedules.delete_of_bot(bot_id)
        logger.info("bot %s, its chat and its schedules deleted", bot_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    def _refuse_unsaved_model(self, name: SecretName | None) -> None:
        """Raise a 422 when `name` is not a saved LLM credential; `None` is no model, and passes."""
        reason = None if name is None else self._secrets.not_a_model_reason(name)
        if reason is not None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=reason)

    async def _stop_speaking(self, bot_id: str) -> None:
        """End the bot's own chat's turn, and the discussion of any group it is speaking in."""
        for chat_id in {self._bots.chat_of(bot_id), *self._runs.chats_spoken_in(bot_id)}:
            await self._runs.stop(chat_id)
