"""Bots: a name, the instructions it answers with, its own chat, and the groups it is in."""

from harness.bots.domain.models import (
    ASSISTANT_ID,
    BUILDER_ID,
    BUILDER_NAME,
    Bot,
    BotDraft,
    BotEdit,
    BotNotFound,
    BuiltInBotError,
    ChatMembers,
    EmptyGroupError,
    Group,
    GroupDraft,
    GroupMemberNotFound,
    UnsavedModelError,
)
from harness.bots.repository.bot_repository import BotRepository
from harness.bots.repository.group_repository import GroupRepository
from harness.bots.service.bot_service import BotService
from harness.bots.service.group_service import GroupService

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
    "ChatMembers",
    "Group",
    "GroupDraft",
    "GroupMemberNotFound",
    "GroupRepository",
    "EmptyGroupError",
    "GroupService",
    "UnsavedModelError",
]
