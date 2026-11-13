"""The save behind `POST /api/bots`, a tool offered while an LLM credential is saved."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, create_model

from harness.bots import BotDraft, BotService
from harness.secrets import SecretService
from harness.tools.domain.context import ToolContext
from harness.tools.domain.outcome import INVALID_ARGUMENTS, Failure, Ok, ToolOutcome
from harness.tools.domain.tool import Tool

BOT_CREATE = "bot_create"

_DESCRIPTION = (
    "Make a new bot when the user asks for one: a teammate with its own name, its own "
    "instructions, its own model and its own chat, listed under Bots in the sidebar, the same "
    "as one made with the New bot button. Making it is the whole action; tell the user it is "
    "there."
)


def bot_create_tool(bots: BotService, secrets: SecretService) -> Tool[BotDraft] | None:
    """The tool that makes a bot as `POST /api/bots` does; `None` while no LLM credential is."""
    names = secrets.model_credential_names()
    if not names:
        return None

    async def execute(args: BotDraft, _context: ToolContext) -> ToolOutcome:
        reason = secrets.not_a_model_reason(args.model)
        if reason is not None:
            return Failure(INVALID_ARGUMENTS, reason)
        bot = await bots.create(args)
        return Ok(f"made bot {bot.name!r} (id {bot.id}); its chat is under Bots in the sidebar")

    return Tool.from_model(
        name=BOT_CREATE, description=_DESCRIPTION, args_model=_args_model(names), execute=execute
    )


def _args_model(names: tuple[str, ...]) -> type[BotDraft]:
    """`BotDraft` with `model` as an enum of the saved LLM credentials' names."""
    return create_model(
        "BotDraft",
        __base__=BotDraft,
        __doc__=BotDraft.__doc__,
        model=(
            Literal[names],
            Field(
                description="The saved LLM credential the bot answers on.",
                json_schema_extra=_always_enum(names),
            ),
        ),
    )


def _always_enum(names: tuple[str, ...]):
    """A schema hook that forces `enum` for `model`."""
    # Pydantic prints a one-member `Literal` as `const`, not `enum`.

    def fix(schema: dict) -> None:
        schema.pop("const", None)
        schema["enum"] = list(names)

    return fix
