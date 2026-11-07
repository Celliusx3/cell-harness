"""A server's status: whether it came up, and the tools it offers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Status = Literal["waiting", "connecting", "connected", "failed", "disconnected"]


@dataclass(frozen=True)
class ServerStatus:
    """One connection as the outside world sees it."""

    id: str
    status: Status
    error: str
    tool_names: tuple[str, ...]
