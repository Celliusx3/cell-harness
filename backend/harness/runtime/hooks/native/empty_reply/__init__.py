"""The model replied with nothing: no text, no tool call."""

from harness.runtime.hooks.native.empty_reply.hook import (
    EMPTY_REPLY_REASON,
    EmptyReplyHook,
)

__all__ = [
    "EMPTY_REPLY_REASON",
    "EmptyReplyHook",
]
