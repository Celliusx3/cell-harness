"""Compaction: the loop's answer to a conversation that outgrows the window."""

from __future__ import annotations

from harness.agent.compaction.service import (
    CompactionEvent,
    CompactionRefused,
    check_can_compact,
    run_compaction,
    should_compact,
)

__all__ = [
    "CompactionEvent",
    "CompactionRefused",
    "check_can_compact",
    "run_compaction",
    "should_compact",
]
