"""The bots: list, make, edit, archive, restore or delete one, and choose its keys."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Response, status

from harness.bots import Bot, BotDraft, BotEdit, BotService
from harness.bots.router.schemas import AllowedSecrets
from harness.bots.service.bot_lifecycle_service import BotLifecycleService

logger = logging.getLogger(__name__)


class BotRouter:
    """Every bot over HTTP, and each change a person can make to one."""

    def __init__(self, bots: BotService, lifecycle: BotLifecycleService) -> None:
        self._bots = bots
        self._lifecycle = lifecycle
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
        return list(self._bots.active_bots())

    async def list_archived_bots(self) -> list[Bot]:
        return list(self._bots.archived_bots())

    async def create_bot(self, body: BotDraft) -> Bot:
        bot = await self._lifecycle.create(body)
        logger.info("bot %s created", bot.id)
        return bot

    async def update_bot(self, bot_id: str, body: BotEdit) -> Bot:
        bot = self._lifecycle.update(bot_id, body)
        logger.info("bot %s saved, answering on %s", bot_id, bot.model_credential)
        return bot

    async def set_bot_secrets(self, bot_id: str, body: AllowedSecrets) -> Bot:
        bot = self._lifecycle.set_allowed_secrets(bot_id, body.names)
        logger.info("bot %s may use %s", bot_id, list(bot.secret_names))
        return bot

    async def archive_bot(self, bot_id: str) -> Response:
        await self._lifecycle.archive(bot_id)
        logger.info("bot %s archived", bot_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def restore_bot(self, bot_id: str) -> Response:
        self._bots.restore(bot_id)
        logger.info("bot %s restored", bot_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def delete_bot(self, bot_id: str) -> Response:
        await self._lifecycle.delete(bot_id)
        logger.info("bot %s, its chat and its schedules deleted", bot_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
