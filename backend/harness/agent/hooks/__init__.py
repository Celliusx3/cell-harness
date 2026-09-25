"""Hooks around a tool call, and the machinery that runs them."""

from harness.agent.hooks.calls import CompletedCall, Signature, completed_calls
from harness.agent.hooks.chain import (
    GiveUp,
    HookChain,
    StepDecision,
    StepHook,
    Tell,
    ToolHook,
)

__all__ = [
    "HookChain",
    "CompletedCall",
    "GiveUp",
    "Signature",
    "StepDecision",
    "StepHook",
    "Tell",
    "ToolHook",
    "completed_calls",
]
