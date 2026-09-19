"""Making `harness.*` log lines visible under uvicorn."""

from __future__ import annotations

import logging


def configure_logging() -> None:
    """Make `harness.*` log lines visible when running under uvicorn."""
    harness = logging.getLogger("harness")
    if harness.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
    harness.addHandler(handler)
    harness.setLevel(logging.INFO)
