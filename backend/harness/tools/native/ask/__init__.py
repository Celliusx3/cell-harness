"""The model's ask tools: one question to the bot's own model, or a jobs file of them."""

from harness.tools.native.ask._call import model_reply
from harness.tools.native.ask.tools import (
    ASK_MODEL,
    ASK_MODEL_JOBS,
    ask_model_jobs_tool,
    ask_model_tool,
)

__all__ = [
    "ASK_MODEL",
    "ASK_MODEL_JOBS",
    "ask_model_jobs_tool",
    "ask_model_tool",
    "model_reply",
]
