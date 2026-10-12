"""Bots: a name, the instructions it answers with, its own chat, and the groups it is in."""

from harness.bots.models import (
    ASSISTANT_ID,
    ASSISTANT_INSTRUCTIONS,
    BUILDER_ID,
    BUILDER_INSTRUCTIONS,
    BUILDER_NAME,
    Bot,
    BotDraft,
    BotNotFound,
    BotPermanent,
    ChatMembers,
    Group,
    GroupDraft,
    GroupEmpty,
)
from harness.bots.service import BotService, roster

__all__ = [
    "ASSISTANT_ID",
    "ASSISTANT_INSTRUCTIONS",
    "BUILDER_ID",
    "BUILDER_INSTRUCTIONS",
    "BUILDER_NAME",
    "Bot",
    "BotDraft",
    "BotNotFound",
    "BotPermanent",
    "BotService",
    "ChatMembers",
    "Group",
    "GroupDraft",
    "GroupEmpty",
    "roster",
]
