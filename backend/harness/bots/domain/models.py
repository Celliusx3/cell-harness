"""What a bot is, what the bots file holds, and how a change to a bot is refused."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from harness.secrets import CredentialKind, SecretName

ASSISTANT_ID = "assistant"
ASSISTANT_NAME = "Assistant"
BUILDER_ID = "builder"
BUILDER_NAME = "Bot builder"
MENTION_PATTERN = r"(?:^|[^\w-])@{name}(?![\w-])"


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
    """What Edit bot saves: name, instructions, model (`None`: none) and worker limit."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: NonBlankText
    instructions: NonBlankText
    model: SecretName | None
    max_workers: int = Field(ge=MIN_WORKERS, le=MAX_WORKERS)


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

    def is_mentioned_in(self, text: str) -> bool:
        """Whether `text` holds `@` and this bot's name in any case, not inside a longer word."""
        name = self.name.strip()
        if not name:
            return False
        pattern = MENTION_PATTERN.format(name=re.escape(name))
        return re.search(pattern, text, re.IGNORECASE) is not None

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


class BotsFile(BaseModel):
    """The bots file: every stored bot, in the order it was made."""

    model_config = ConfigDict(frozen=True)

    bots: tuple[Bot, ...] = ()


class BotNotFound(LookupError):
    """No bot has that id."""

    def __init__(self, bot_id: str) -> None:
        super().__init__(f"no bot {bot_id!r}")


class BuiltInBotError(PermissionError):
    """A built-in bot cannot be archived or deleted."""

    def __init__(self, bot_id: str) -> None:
        super().__init__(f"{bot_id!r} is built in and cannot be archived or deleted")


class UnsavedModelError(ValueError):
    """The model asked for a bot is not a saved LLM credential; the message says which are."""
