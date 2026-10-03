"""Compaction: the loop's answer to a conversation that outgrows the window."""

from __future__ import annotations

from harness.agent.compaction.service import (
    CompactionEvent,
    CompactionRefused,
    CompactionService,
)

__all__ = ["CompactionEvent", "CompactionRefused", "CompactionService"]
