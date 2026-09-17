"""Compaction: the loop's answer to a conversation that outgrows the window."""

from __future__ import annotations

from harness.agent.compaction.prune import PRUNE_KEEP
from harness.agent.compaction.service import (
    COMPACT_AT,
    NOTHING,
    UNANSWERED,
    CompactionRefused,
    CompactionService,
)

__all__ = [
    "COMPACT_AT",
    "NOTHING",
    "PRUNE_KEEP",
    "UNANSWERED",
    "CompactionRefused",
    "CompactionService",
]
