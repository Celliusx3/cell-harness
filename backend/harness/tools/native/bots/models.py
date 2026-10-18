"""What `message_bot` is called with."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


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
