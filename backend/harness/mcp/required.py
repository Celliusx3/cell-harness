"""Whether the servers the app cannot serve without came up, and what to say when they did not."""

from __future__ import annotations

from collections.abc import Sequence

from harness.mcp.models.status import ServerStatus


def required_refusal(statuses: Sequence[ServerStatus], waited_seconds: float) -> str | None:
    """Why the app must not serve, naming each required server that is not connected."""
    reasons = [_reason(status, waited_seconds) for status in statuses]
    named = [reason for reason in reasons if reason is not None]
    return "; ".join(named) if named else None


def _reason(status: ServerStatus, waited_seconds: float) -> str | None:
    if status.status == "connected":
        return None
    if status.status == "connecting":
        return f"{status.id} is required and did not connect within {waited_seconds:g}s"
    return f"{status.id} is required and failed to connect: {status.error}"
