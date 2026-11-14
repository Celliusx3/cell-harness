"""What a bot and a group are, what the bots file holds, and how a change to them is refused."""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from harness.secrets import CredentialKind, SecretName

ASSISTANT_ID = "assistant"
ASSISTANT_NAME = "Assistant"
BUILDER_ID = "builder"
BUILDER_NAME = "Bot builder"
MIN_GROUP_MEMBERS = 2
MAX_GROUP_MEMBERS = 6


def _strip_and_refuse_blank(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


NonBlankText = Annotated[str, AfterValidator(_strip_and_refuse_blank)]


MIN_WORKERS, DEFAULT_MAX_WORKERS, MAX_WORKERS = 1, 3, 16


class BotDraft(BaseModel):
    """A new bot's name, instructions and model, from the API or a tool call."""

    model_config = ConfigDict(frozen=True)

    name: NonBlankText = Field(description="The name the sidebar shows, e.g. 'Researcher'.")
    instructions: NonBlankText = Field(
        description=(
            "What the bot is told before every turn in its chat, written to it as 'you', "
            "e.g. 'You find sources for a question and cite every claim.'"
        )
    )
    model: SecretName = Field(description="The saved LLM credential the bot answers on.")


class BotEdit(BaseModel):
    """What Edit bot saves: name, instructions, model (`None`: none), workers (`None`: kept)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: NonBlankText
    instructions: NonBlankText
    model: SecretName | None
    max_workers: int | None = Field(default=None, ge=MIN_WORKERS, le=MAX_WORKERS)


class Bot(BaseModel):
    """A name, instructions, keys, model, worker limit, and its chat, whose id is its id."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    instructions: str
    archived: bool = False
    secret_names: tuple[SecretName, ...] = ()
    model_credential: SecretName | None = None
    max_workers: int = Field(default=DEFAULT_MAX_WORKERS, ge=MIN_WORKERS, le=MAX_WORKERS)

    def can_use_secret(self, name: SecretName) -> bool:
        """Whether the saved key `name` is one of the keys this bot may use."""
        return name in self.secret_names

    def has_credential(self, name: SecretName, kind: CredentialKind) -> bool:
        """Whether the credential `name` of `kind` is one of its keys or its model; else no."""
        if kind == "custom":
            return self.can_use_secret(name)
        return kind == "llm" and self.model_credential == name

    def with_secret(self, name: SecretName, *, allowed: bool) -> Bot:
        """This bot with the key `name` among its keys, last, or off them."""
        kept = tuple(key for key in self.secret_names if key != name)
        return self.model_copy(update={"secret_names": (*kept, name) if allowed else kept})

    def without_credential(self, name: SecretName) -> Bot:
        """This bot with the credential `name` off its keys and off its model."""
        return self.with_secret(name, allowed=False).model_copy(
            update={
                "model_credential": None if self.model_credential == name else self.model_credential
            }
        )


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


class BotsFile(BaseModel):
    """The bots file: every stored bot and every group, each in the order it was made."""

    model_config = ConfigDict(frozen=True)

    bots: tuple[Bot, ...] = ()
    groups: tuple[Group, ...] = ()

    def active_bots(self, built_ins: tuple[Bot, ...]) -> tuple[Bot, ...]:
        """Each built-in as stored, else its default, then the stored others not archived."""
        built_in_ids = {default.id for default in built_ins}
        stored_built_ins = (
            next((bot for bot in self.bots if bot.id == default.id), default)
            for default in built_ins
        )
        others = (bot for bot in self.bots if bot.id not in built_in_ids and not bot.archived)
        return (*stored_built_ins, *others)

    def with_bots(self, bots: tuple[Bot, ...]) -> BotsFile:
        """This file with each of `bots` in its stored place, and those not yet stored first."""
        by_id = {bot.id: bot for bot in bots}
        stored_ids = {stored.id for stored in self.bots}
        added = tuple(bot for bot in bots if bot.id not in stored_ids)
        replaced = tuple(by_id.get(stored.id, stored) for stored in self.bots)
        return self.model_copy(update={"bots": (*added, *replaced)})

    def with_archived(self, bot_id: str, *, archived: bool) -> BotsFile:
        """This file with the stored bot `bot_id` archived or not; `BotNotFound` when unknown."""
        if bot_id not in {bot.id for bot in self.bots}:
            raise BotNotFound(bot_id)
        bots = tuple(
            bot.model_copy(update={"archived": archived}) if bot.id == bot_id else bot
            for bot in self.bots
        )
        return self.model_copy(update={"bots": bots})


class BotNotFound(LookupError):
    """No bot has that id."""

    def __init__(self, bot_id: str) -> None:
        super().__init__(f"no bot {bot_id!r}")


class BuiltInBotError(PermissionError):
    """A built-in bot cannot be archived or deleted."""

    def __init__(self, bot_id: str) -> None:
        super().__init__(f"{bot_id!r} is built in and cannot be archived or deleted")


class EmptyGroupError(LookupError):
    """Every member of this group has been archived or deleted."""

    def __init__(self, group_id: str) -> None:
        super().__init__(f"every member of group {group_id!r} is archived or deleted")
