"""Compaction: the loop's answer to a conversation that outgrows the window."""

from __future__ import annotations

from harness.runtime.compaction.service import (
    CompactionEvent,
    CompactionRefusedError,
    check_can_compact,
    run_compaction,
    should_compact,
)

__all__ = [
    "CompactionEvent",
    "CompactionRefusedError",
    "check_can_compact",
    "run_compaction",
    "should_compact",
]
