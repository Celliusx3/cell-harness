"""The keyring's rules, held over its repository: one site per name, a cap, each key sealed."""

from __future__ import annotations

import os

from pydantic import SecretStr

from harness.secrets.encryption import seal, unseal
from harness.secrets.models import (
    Destination,
    SealedSecret,
    Secret,
    SecretNotFound,
    SecretRefused,
    SecretSummary,
)
from harness.secrets.repository import SecretRepository

RECORD_ID_BYTES = 12
MAX_SECRETS = 100


class SecretService:
    """Every saved key, sealed for its own record, kept by the rules in a `SecretRepository`."""

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
        sealed = SealedSecret(
            id=record_id,
            name=name,
            destination=destination,
            ciphertext=seal(
                value.get_secret_value(),
                encryption_key=self._encryption_key,
                record_id=record_id,
            ),
        )
        self._repository.replace_all(
            (*(secret for secret in stored if secret is not existing), sealed)
        )

    def find(self, name: str) -> Secret | None:
        """The key called `name`, unsealed, or `None` when none is saved."""
        sealed = next((s for s in self._repository.sealed_secrets() if s.name == name), None)
        if sealed is None:
            return None
        plaintext = unseal(
            sealed.ciphertext, encryption_key=self._encryption_key, record_id=sealed.id
        )
        return Secret(destination=sealed.destination, value=SecretStr(plaintext))

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
