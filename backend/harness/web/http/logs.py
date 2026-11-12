"""Making `harness.*` log lines visible under uvicorn."""

from __future__ import annotations

import logging

TOKEN_URL_LOGGERS = ("httpx", "telegram")


def configure_logging() -> None:
    """Make `harness.*` log lines visible when running under uvicorn."""
    keep_token_urls_out()
    harness = logging.getLogger("harness")
    if harness.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
    harness.addHandler(handler)
    harness.setLevel(logging.INFO)


def keep_token_urls_out() -> None:
    """Hush, below a warning, the libraries that log a URL: a Telegram bot's holds its token."""
    for name in TOKEN_URL_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
