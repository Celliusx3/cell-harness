"""Which model a bot's turns ask: a client and the model to name to it, or none picked."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from harness.llm import LLMClient

PICK_A_MODEL = "Pick a model for this bot in Edit bot."


@dataclass(frozen=True)
class ModelChoice:
    """The client a request goes through, and the model it names there."""

    client: LLMClient
    model: str


@dataclass(frozen=True)
class NoModel:
    """The bot has no model to ask: none picked, or the one picked was removed."""


class BotModels(Protocol):
    """Each bot's model, asked afresh by every turn and every compaction."""

    async def model_for(self, bot_id: str | None) -> ModelChoice | NoModel:
        """The model `bot_id` asks; `NoModel` for no bot, an unknown one, or one with none."""
        ...
