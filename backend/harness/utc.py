"""UTC as the model and the tools read it: one format, shared by every module that writes it."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_text(instant: datetime) -> str:
    """`instant` in ISO 8601 UTC, to the second, with a trailing Z."""
    return instant.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
