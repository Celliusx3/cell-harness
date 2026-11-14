"""Saving a bot as Edit bot does, with one thing changed and the rest as it was."""

from __future__ import annotations

from pathlib import Path

from harness.bots import ASSISTANT_ID, Bot, BotEdit, BotService
from harness.secrets import SecretService
from tests.webapp import MODEL_CREDENTIAL, a_model_saved_in


def assistant_on_a_model(tmp_path: Path, bots: BotService) -> SecretService:
    """`a_model_saved_in`, with Assistant's turns asking that credential."""
    secrets = a_model_saved_in(tmp_path)
    put_on_model(bots, ASSISTANT_ID, MODEL_CREDENTIAL)
    return secrets


def put_on_model(bots: BotService, bot_id: str, name: str | None) -> Bot:
    """Save the bot as Edit bot does, changing only its model to `name`."""
    bot = bots.active_bot(bot_id)
    edit = BotEdit(
        name=bot.name, instructions=bot.instructions, model=name, max_workers=bot.max_workers
    )
    return bots.update(bot_id, edit)


def put_instructions(bots: BotService, bot_id: str, instructions: str) -> Bot:
    """Save the bot as Edit bot does, changing only its instructions to `instructions`."""
    bot = bots.active_bot(bot_id)
    edit = BotEdit(
        name=bot.name,
        instructions=instructions,
        model=bot.model_credential,
        max_workers=bot.max_workers,
    )
    return bots.update(bot_id, edit)
