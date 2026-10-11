"""The model's way to make a bot, through the same save as `POST /api/bots`."""

from harness.tools.native.bots.tools import BOT_CREATE, bot_create_tool

__all__ = ["BOT_CREATE", "bot_create_tool"]
