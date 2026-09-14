"""Making `harness.*` log lines visible under uvicorn."""

from __future__ import annotations

import logging


def configure_logging() -> None:
    """Make `harness.*` log lines visible when running under uvicorn.

    Uvicorn configures only its own loggers, so without this everything this
    codebase logs — a tool provider that raised, a run that failed, a channel
    that stopped polling — is written to a logger with no handler and vanishes.
    That is how a dead Telegram poller came to look like a working one.

    Called by `create_web_app`, **not at import**: configuring logging is the application's
    business, and a library that did it on import would fight whatever imported
    it.
    """
    harness = logging.getLogger("harness")
    if harness.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
    harness.addHandler(handler)
    harness.setLevel(logging.INFO)
