"""The bot page's list of saved keys: every custom key, its site, and the bots allowed to use it."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from harness.bots import Bot, BotService
from harness.secrets import Destination, SecretService, SecretSummary


class AllowedBot(BaseModel):
    """A bot that may use a key: its id and the name the sidebar shows."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str


class SavedKey(Destination):
    """One saved key as the bot page lists it: its name, its site and its bots, never its value."""

    name: str
    bots: tuple[AllowedBot, ...]


def build_router(secrets: SecretService, bots: BotService) -> APIRouter:
    """List the keyring's custom keys, each with the bots allowed to use it."""
    router = APIRouter(prefix="/api/secrets", tags=["secrets"])

    @router.get("", response_model=list[SavedKey])
    async def list_secrets() -> list[SavedKey]:
        active = await bots.active_bots()
        return [_saved_key(summary, active) for summary in secrets.summaries()]

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
