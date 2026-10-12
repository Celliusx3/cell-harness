"""What a bot and a group are, what the bots file holds, and how a change to them is refused."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from harness.secrets import SecretName

ASSISTANT_ID = "assistant"
ASSISTANT_NAME = "Assistant"
ASSISTANT_INSTRUCTIONS = "You are a helpful assistant."
BUILDER_ID = "builder"
BUILDER_NAME = "Bot builder"
BUILDER_INSTRUCTIONS = (
    "You are Bot builder. You help the user make a new bot. Find out what it is for, then ask "
    "at most two more questions, each with ask_user, never as a list in your reply. Then call "
    'bot_create once. Its instructions speak to the bot as "you" and carry every answer the '
    "user gave, in their words. If the user denies it, ask what to change."
)
MIN_MEMBERS = 2
MAX_MEMBERS = 6


class BotDraft(BaseModel):
    """A bot's name and instructions from the form or a tool call, stripped and not blank."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="The name the sidebar shows, e.g. 'Researcher'.")
    instructions: str = Field(
        description=(
            "What the bot is told before every turn in its chat, written to it as 'you', "
            "e.g. 'You find sources for a question and cite every claim.'"
        )
    )

    @field_validator("name", "instructions")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        """Strip the text, and refuse what is left empty."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class Bot(BaseModel):
    """A name, its instructions, the saved keys it may use, and its one chat, whose id is its id."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    instructions: str
    archived: bool = False
    secret_names: tuple[SecretName, ...] = ()


class GroupDraft(BaseModel):
    """A group's name, stripped and not blank, and two to six different bots' ids."""

    model_config = ConfigDict(frozen=True)

    name: str
    member_ids: tuple[str, ...] = Field(min_length=MIN_MEMBERS, max_length=MAX_MEMBERS)

    @field_validator("name")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        """Strip the name, and refuse what is left empty."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("member_ids")
    @classmethod
    def _once_each(cls, value: tuple[str, ...]) -> tuple[str, ...]:
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


class BotsFile(BaseModel):
    """The bots file: every stored bot and every group, each in the order it was made."""

    model_config = ConfigDict(frozen=True)

    bots: tuple[Bot, ...] = ()
    groups: tuple[Group, ...] = ()


class BotNotFound(LookupError):
    """No bot has that id."""

    def __init__(self, bot_id: str) -> None:
        super().__init__(f"no bot {bot_id!r}")


class BotPermanent(PermissionError):
    """A built-in bot cannot be archived or deleted."""

    def __init__(self, bot_id: str) -> None:
        super().__init__(f"{bot_id!r} is built in and cannot be archived or deleted")


class GroupEmpty(LookupError):
    """Every member of this group has been archived or deleted."""

    def __init__(self, group_id: str) -> None:
        super().__init__(f"every member of group {group_id!r} is archived or deleted")
