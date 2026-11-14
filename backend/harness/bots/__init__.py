"""Bots: a name, the instructions it answers with, and its own chat."""

from harness.bots.domain.models import (
    ASSISTANT_ID,
    BUILDER_ID,
    BUILDER_NAME,
    Bot,
    BotDraft,
    BotEdit,
    BotNotFound,
    BuiltInBotError,
    UnsavedModelError,
)
from harness.bots.repository.bot_repository import BotRepository
from harness.bots.service.bot_service import BotService

__all__ = [
    "ASSISTANT_ID",
    "BUILDER_ID",
    "BUILDER_NAME",
    "Bot",
    "BotDraft",
    "BotEdit",
    "BotNotFound",
    "BuiltInBotError",
    "BotRepository",
    "BotService",
    "UnsavedModelError",
]
