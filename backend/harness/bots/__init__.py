"""Bots: a name, the instructions it answers with, its own chat, and the groups it is in."""

from harness.bots.models import (
    ASSISTANT_ID,
    BUILDER_ID,
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
from harness.bots.service import BotService, bot_instructions_event, group_members_event

__all__ = [
    "ASSISTANT_ID",
    "BUILDER_ID",
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
    "bot_instructions_event",
    "group_members_event",
]
