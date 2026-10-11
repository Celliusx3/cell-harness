"""`ask_for_secret` and `fetch_with_secret` — a key the person saves, used unseen by the model."""

from harness.tools.native.secrets.models import SavedName, SecretAsk
from harness.tools.native.secrets.tools import (
    ASK_FOR_SECRET,
    ASK_FOR_SECRET_TOOL,
    FETCH_WITH_SECRET,
    fetch_with_secret_tool,
)

__all__ = [
    "ASK_FOR_SECRET",
    "ASK_FOR_SECRET_TOOL",
    "FETCH_WITH_SECRET",
    "SavedName",
    "SecretAsk",
    "fetch_with_secret_tool",
]
