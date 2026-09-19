"""Hooks around a tool call, and the machinery that runs them."""

from harness.agent.hooks.calls import CompletedCall, Signature, completed_calls
from harness.agent.hooks.chain import HOOK_TIMEOUT_S, HookChain, ToolHook

__all__ = [
    "HOOK_TIMEOUT_S",
    "HookChain",
    "CompletedCall",
    "Signature",
    "ToolHook",
    "completed_calls",
]
