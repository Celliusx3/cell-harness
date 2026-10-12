"""The model's way to make a bot, through the same save as `POST /api/bots`, and to message one."""

from harness.tools.native.bots.message import MESSAGE_BOT, message_bot_tool
from harness.tools.native.bots.tools import BOT_CREATE, bot_create_tool

__all__ = ["BOT_CREATE", "MESSAGE_BOT", "bot_create_tool", "message_bot_tool"]
