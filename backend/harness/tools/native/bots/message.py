"""`message_bot`: a message into another bot's own chat, whose answer arrives later on its own."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, create_model

from harness.bots import BotService
from harness.tools.definition import ToolDefinition
from harness.tools.models.context import ToolContext
from harness.tools.models.outcome import Failure, Ok, ToolOutcome

MESSAGE_BOT = "message_bot"

_DESCRIPTION = (
    "Send a message to another of the user's bots, into that bot's own chat. Call it when "
    "another bot is better placed to answer or to do part of the work, or when the user asks "
    "you to ask one. It does not wait for an answer: it returns once the message is sent, and "
    "the bot's final reply arrives later as a new message that wakes you. After sending, carry "
    "on with anything that does not need the answer, and tell the user who you asked."
)


class MessageBotArgs(BaseModel):
    """What the model passes to `message_bot`."""

    model_config = ConfigDict(frozen=True)

    bot: str
    message: str = Field(
        description=(
            "The whole message. The other bot sees none of this conversation, so say "
            "everything it needs."
        )
    )


class BotMessageSender(Protocol):
    """Queues a message for the active bot named `to_name`, from the turn that made `call_id`."""

    async def send(
        self, call_id: str, *, from_bot_id: str, to_name: str, text: str
    ) -> Ok | Failure: ...


def message_bot_tool(
    bots: BotService, messages: BotMessageSender
) -> ToolDefinition[MessageBotArgs]:
    """The tool that sends a message to one of the bots active now, and returns once it is sent."""

    async def execute(args: MessageBotArgs, context: ToolContext) -> ToolOutcome:
        return await messages.send(
            context.call_id, from_bot_id=context.origin.bot_id, to_name=args.bot, text=args.message
        )

    return ToolDefinition.from_model(
        name=MESSAGE_BOT,
        description=_DESCRIPTION,
        args_model=_args_model(bots.active_bot_names()),
        execute=execute,
    )


def _args_model(names: tuple[str, ...]) -> type[MessageBotArgs]:
    """`MessageBotArgs` with `bot` as an enum of the active bots' names."""
    return create_model(
        "MessageBotArgs",
        __base__=MessageBotArgs,
        bot=(
            Literal[names],
            Field(
                description=(
                    "The name of the bot to send to, exactly as listed. Never your own name."
                )
            ),
        ),
    )
