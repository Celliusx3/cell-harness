"""Show comic pages part by part, erase the text the model points at, and letter its English."""

from __future__ import annotations


class ComicError(RuntimeError):
    """This command's work cannot be done; the message says why."""
