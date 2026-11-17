"""Why a run cannot start."""

from __future__ import annotations


class RunAlreadyActiveError(RuntimeError):
    """This conversation is already running a turn."""
