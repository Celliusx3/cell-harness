"""Which model a bot's turns ask: a client, and the model to name to it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from harness.llm import LLMClient


@dataclass(frozen=True)
class ModelChoice:
    """The client a request goes through, and the model it names there."""

    client: LLMClient
    model: str


class BotModels(Protocol):
    """Each bot's model, asked afresh by every turn and every compaction."""

    async def model_for(self, bot_id: str | None) -> ModelChoice:
        """The model `bot_id` asks; `None`, for no known bot, gets the Default model."""
        ...
