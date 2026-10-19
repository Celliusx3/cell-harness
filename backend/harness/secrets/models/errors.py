"""Why a key cannot be saved, or cannot be found."""

from __future__ import annotations


class SecretRefused(ValueError):
    """A key that cannot be saved; the message never holds the key."""


class SecretNotFound(LookupError):
    """No key is saved under that name."""

    def __init__(self, name: str) -> None:
        super().__init__(f"no saved key named {name!r}")
