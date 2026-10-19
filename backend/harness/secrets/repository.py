"""Where the keyring is kept: every saved key, sealed, read and replaced whole."""

from __future__ import annotations

from typing import Protocol

from harness.secrets.models import SealedSecret


class SecretRepository(Protocol):
    """The keyring's sealed keys, as storage."""

    def sealed_secrets(self) -> tuple[SealedSecret, ...]:
        """Every saved key, sealed; `()` when there is no file."""
        ...

    def replace_all(self, secrets: tuple[SealedSecret, ...]) -> None:
        """The keyring replaced whole by `secrets`."""
        ...
