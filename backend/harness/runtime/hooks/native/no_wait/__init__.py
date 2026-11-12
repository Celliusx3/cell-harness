"""The orchestrator waiting in its own turn for what arrives by itself."""

from harness.runtime.hooks.native.no_wait.hook import NoWaitHook, waits

__all__ = ["NoWaitHook", "waits"]
