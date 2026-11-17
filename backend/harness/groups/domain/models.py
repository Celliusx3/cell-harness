"""What a group is, what the groups file holds, and how a change to a group is refused."""

from __future__ import annotations

from collections.abc import Sequence, Set

from pydantic import BaseModel, ConfigDict, Field, field_validator

from harness.bots.domain.models import Bot, BotNotFound, NonBlankText

MIN_GROUP_MEMBERS = 2
MAX_GROUP_MEMBERS = 6


class GroupDraft(BaseModel):
    """A group's name, stripped and not blank, and two to six different bots' ids."""

    model_config = ConfigDict(frozen=True)

    name: NonBlankText
    member_ids: tuple[str, ...] = Field(min_length=MIN_GROUP_MEMBERS, max_length=MAX_GROUP_MEMBERS)

    @field_validator("member_ids")
    @classmethod
    def _refuse_repeats(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Refuse a bot named twice."""
        if len(set(value)) != len(value):
            raise ValueError("each bot can be a member once")
        return value


class Group(BaseModel):
    """Bots sharing one chat, whose id is the group's id; they answer in `member_ids` order."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    member_ids: tuple[str, ...]


class ChatMembers(BaseModel):
    """Who answers in one chat: a bot's own chat has no group and that one bot."""

    model_config = ConfigDict(frozen=True)

    group: Group | None
    bots: tuple[Bot, ...]


class GroupsFile(BaseModel):
    """The groups file: every group, in the order it was made."""

    model_config = ConfigDict(frozen=True)

    groups: tuple[Group, ...] = ()


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


def groups_left_without_members(
    groups: Sequence[Group], *, stored_bot_ids: Set[str]
) -> tuple[Group, ...]:
    """The groups none of whose members is a stored bot any more; an archived one still is."""
    return tuple(g for g in groups if not any(m in stored_bot_ids for m in g.member_ids))
