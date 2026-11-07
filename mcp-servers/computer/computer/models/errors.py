"""How reaching the PC fails, whatever the engine."""

from __future__ import annotations


class EngineError(RuntimeError):
    """The engine refused, or could not be reached. The message says which, in its own words."""


class EngineTimeout(EngineError):
    """The engine did not answer in time."""
