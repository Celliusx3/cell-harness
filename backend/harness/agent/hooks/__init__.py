"""Hooks around a tool call, and the machinery that runs them.

`chain.py` is the contract — `ToolHook`, two typed decisions, `pre` and
`post` — and `HookChain`, which folds the session once and runs many hooks as
one under a timeout, failing open. `calls.py` is the fold. A hook implemented
in this process goes in `native/<name>/`, the way a native tool does; the
composition root picks which to install and in what order.
"""

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
