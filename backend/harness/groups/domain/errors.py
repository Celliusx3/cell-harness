"""Why a group cannot be made, or a chat has nobody to answer."""

from __future__ import annotations

from harness.bots.domain.models import BotNotFound


class GroupMemberNotFound(BotNotFound):
    """A bot named as a group's member is no active bot."""


class EmptyGroupError(LookupError):
    """Every member of this group has been archived or deleted."""

    def __init__(self, group_id: str) -> None:
        super().__init__(f"every member of group {group_id!r} is archived or deleted")


class NotAChatMemberError(LookupError):
    """The bot named to speak is no active bot answering in this chat."""

    def __init__(self, chat_id: str, bot_id: str) -> None:
        super().__init__(f"bot {bot_id!r} is no active member of chat {chat_id!r}")


class GroupNotFound(LookupError):
    """No group has this id."""

    def __init__(self, group_id: str) -> None:
        super().__init__(f"no group {group_id!r}")
