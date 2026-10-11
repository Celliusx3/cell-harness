"""What a bot is, what the bots file holds, and how a change to them is refused."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
    """A name, the instructions it answers with, and its one chat, whose id is the bot's."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    instructions: str
    archived: bool = False


class BotsFile(BaseModel):
    """The bots file: every stored bot, in the order each was made."""

    model_config = ConfigDict(frozen=True)

    bots: tuple[Bot, ...] = ()


class BotNotFound(LookupError):
    """No bot has that id."""

    def __init__(self, bot_id: str) -> None:
        super().__init__(f"no bot {bot_id!r}")


class BotPermanent(PermissionError):
    """A built-in bot cannot be archived or deleted."""

    def __init__(self, bot_id: str) -> None:
        super().__init__(f"{bot_id!r} is built in and cannot be archived or deleted")
