"""The keyring's rules, held over its repository: one site per name, a cap, each key sealed."""

from __future__ import annotations

import os

from pydantic import SecretStr

from harness.secrets.models.destination import Destination
from harness.secrets.models.errors import SecretNotFound, SecretRefused
from harness.secrets.models.sealed import SealedSecret
from harness.secrets.models.secret import Secret, SecretSummary
from harness.secrets.repository import SecretRepository
from harness.secrets.sealing import sealed, unsealed

RECORD_ID_BYTES = 12
MAX_SECRETS = 100


class SecretService:
    """Every saved key, saved and found by the rules, kept through a `SecretRepository`."""

    def __init__(self, repository: SecretRepository, *, encryption_key: str) -> None:
        if not encryption_key.strip():
            raise ValueError("the secrets encryption key must not be blank")
        self._repository = repository
        self._encryption_key = encryption_key

    def save(self, name: str, destination: Destination, value: SecretStr) -> None:
        """Seal `value` as the key `name`; one with the same destination is replaced."""
        stored = self._repository.sealed_secrets()
        existing = next((secret for secret in stored if secret.name == name), None)
        if existing is not None and existing.destination != destination:
            raise SecretRefused(
                f"a key named {name!r} is already saved for {existing.destination.origin}; "
                "remove it before saving it for another site"
            )
        if existing is None and len(stored) >= MAX_SECRETS:
            raise SecretRefused(f"{MAX_SECRETS} keys are already saved; remove one first")
        record_id = os.urandom(RECORD_ID_BYTES).hex()
        sealed_secret = SealedSecret(
            id=record_id,
            name=name,
            destination=destination,
            ciphertext=sealed(
                value.get_secret_value(),
                encryption_key=self._encryption_key,
                record_id=record_id,
            ),
        )
        self._repository.replace_all(
            (*(secret for secret in stored if secret is not existing), sealed_secret)
        )

    def secret_named(self, name: str) -> Secret | None:
        """The key called `name`, unsealed, or `None` when none is saved."""
        sealed_secret = next((s for s in self._repository.sealed_secrets() if s.name == name), None)
        if sealed_secret is None:
            return None
        plaintext = unsealed(
            sealed_secret.ciphertext,
            encryption_key=self._encryption_key,
            record_id=sealed_secret.id,
        )
        return Secret(destination=sealed_secret.destination, value=SecretStr(plaintext))

    def delete(self, name: str) -> None:
        """Remove the key called `name`; `SecretNotFound` when none is saved."""
        stored = self._repository.sealed_secrets()
        kept = tuple(secret for secret in stored if secret.name != name)
        if kept == stored:
            raise SecretNotFound(name)
        self._repository.replace_all(kept)

    def summaries(self) -> tuple[SecretSummary, ...]:
        """Every saved key's name and site, by name; never a value."""
        return tuple(
            SecretSummary(name=secret.name, destination=secret.destination)
            for secret in sorted(self._repository.sealed_secrets(), key=lambda secret: secret.name)
        )
