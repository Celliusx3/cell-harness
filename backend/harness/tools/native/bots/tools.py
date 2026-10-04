"""The New bot form's save, offered to the model as a tool."""

from __future__ import annotations

from harness.bots import BotDraft, BotStore
from harness.tools.context import ToolContext
from harness.tools.definition import Ok, ToolDefinition, ToolOutcome

BOT_CREATE = "bot_create"

_DESCRIPTION = (
    "Make a new bot when the user asks for one: a teammate with its own name, its own "
    "instructions and its own chat, listed under Bots in the sidebar, the same as one made "
    "with the New bot button. Making it is the whole action; tell the user it is there."
)


def bot_create_tool(bots: BotStore) -> ToolDefinition[BotDraft]:
    """The tool that makes a bot through the same save as the New bot form."""

    async def execute(args: BotDraft, _context: ToolContext) -> ToolOutcome:
        bot = await bots.create(args.name, args.instructions)
        return Ok(f"made bot {bot.name!r} (id {bot.id}); its chat is under Bots in the sidebar")

    return ToolDefinition.from_model(
        name=BOT_CREATE, description=_DESCRIPTION, args_model=BotDraft, execute=execute
    )
