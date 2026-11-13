"""What a bot and a group are, what the bots file holds, and how a change to them is refused."""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from harness.secrets import SecretName

ASSISTANT_ID = "assistant"
ASSISTANT_NAME = "Assistant"
BUILDER_ID = "builder"
BUILDER_NAME = "Bot builder"
MIN_MEMBERS = 2
MAX_MEMBERS = 6


def _stripped_not_blank(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


NonBlankText = Annotated[str, AfterValidator(_stripped_not_blank)]


MIN_WORKERS, DEFAULT_WORKERS, MAX_WORKERS = 1, 3, 16
KEY_KIND, MODEL_KIND = "custom", "llm"


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
    max_workers: int = Field(default=DEFAULT_WORKERS, ge=MIN_WORKERS, le=MAX_WORKERS)

    def holds_key(self, name: str) -> bool:
        """Whether the saved key `name` is one of the keys this bot may use."""
        return name in self.secret_names

    def serves(self, name: str, kind: str) -> bool:
        """Whether the credential `name` of `kind` is one of its keys or its model; else no."""
        if kind == KEY_KIND:
            return self.holds_key(name)
        return kind == MODEL_KIND and self.model_credential == name

    def with_key(self, name: str, *, held: bool) -> Bot:
        """This bot with the key `name` among its keys, last, or off them."""
        kept = tuple(key for key in self.secret_names if key != name)
        return self.model_copy(update={"secret_names": (*kept, name) if held else kept})

    def without_credential(self, name: str) -> Bot:
        """This bot with the credential `name` off its keys and off its model."""
        return self.with_key(name, held=False).model_copy(
            update={
                "model_credential": None if self.model_credential == name else self.model_credential
            }
        )


class GroupDraft(BaseModel):
    """A group's name, stripped and not blank, and two to six different bots' ids."""

    model_config = ConfigDict(frozen=True)

    name: NonBlankText
    member_ids: tuple[str, ...] = Field(min_length=MIN_MEMBERS, max_length=MAX_MEMBERS)

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
