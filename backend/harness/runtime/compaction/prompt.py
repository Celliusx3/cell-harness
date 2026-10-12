"""The summary message: what the model reads in place of the compacted history."""

from __future__ import annotations

from collections.abc import Sequence

from harness.prompts import COMPACTION_PREAMBLE, SUMMARY_CLOSE, SUMMARY_OPEN


def summary_message(summary: str, skill_bodies: Sequence[str]) -> str:
    """The message the model reads in place of everything before the boundary."""
    parts = [
        COMPACTION_PREAMBLE,
        f"{SUMMARY_OPEN}\n{summary.strip()}\n{SUMMARY_CLOSE}",
        *skill_bodies,
    ]
    return "\n\n".join(parts)
