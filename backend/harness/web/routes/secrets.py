"""The Keys page: every saved key, the bots allowed to use it, and removing one."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, ConfigDict

from harness.bots import Bot, BotService
from harness.secrets import Destination, SecretService, SecretSummary

logger = logging.getLogger(__name__)


class AllowedBot(BaseModel):
    """A bot that may use a key: its id and the name the sidebar shows."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str


class SavedKey(Destination):
    """One saved key as the Keys page lists it: its name, its site and its bots, never its value."""

    name: str
    bots: tuple[AllowedBot, ...]


def build_router(secrets: SecretService, bots: BotService) -> APIRouter:
    """List the keyring, and remove a key from it and from every bot's list."""
    router = APIRouter(prefix="/api/secrets", tags=["secrets"])

    @router.get("", response_model=list[SavedKey])
    async def list_secrets() -> list[SavedKey]:
        active = await bots.active_bots()
        return [_saved_key(summary, active) for summary in secrets.summaries()]

    @router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_secret(name: str) -> Response:
        secrets.delete(name)
        bots.forget_secret(name)
        logger.info("key %r removed from the keyring and every bot", name)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router


def _saved_key(summary: SecretSummary, bots: tuple[Bot, ...]) -> SavedKey:
    destination = summary.destination
    return SavedKey(
        name=summary.name,
        origin=destination.origin,
        auth=destination.auth,
        header_name=destination.header_name,
        bots=tuple(
            AllowedBot(id=bot.id, name=bot.name) for bot in bots if summary.name in bot.secret_names
        ),
    )
