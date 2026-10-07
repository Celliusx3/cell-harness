"""Bots: a name, the instructions it answers with, and the one chat it answers in."""

from harness.bots.models import (
    ASSISTANT_ID,
    ASSISTANT_INSTRUCTIONS,
    Bot,
    BotDraft,
    BotNotFound,
    BotPermanent,
)
from harness.bots.store import BotStore

__all__ = [
    "ASSISTANT_ID",
    "ASSISTANT_INSTRUCTIONS",
    "Bot",
    "BotDraft",
    "BotNotFound",
    "BotPermanent",
    "BotStore",
]
