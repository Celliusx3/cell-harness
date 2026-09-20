"""Hooks around a tool call, and the machinery that runs them."""

from harness.agent.hooks.calls import CompletedCall, Signature, completed_calls, empty_replies
from harness.agent.hooks.chain import (
    HOOK_TIMEOUT_S,
    GiveUp,
    HookChain,
    StepDecision,
    StepHook,
    Tell,
    ToolHook,
)

__all__ = [
    "HOOK_TIMEOUT_S",
    "HookChain",
    "CompletedCall",
    "GiveUp",
    "Signature",
    "StepDecision",
    "StepHook",
    "Tell",
    "ToolHook",
    "completed_calls",
    "empty_replies",
]
