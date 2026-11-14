"""The orchestrator waiting in its own turn for what arrives by itself."""

from harness.runtime.hooks.native.no_wait.hook import NoWaitHook, is_waiting_call

__all__ = ["NoWaitHook", "is_waiting_call"]
