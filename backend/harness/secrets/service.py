"""The secrets file: the keyring, every key sealed, read on every call."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from pydantic import SecretStr

from harness.secrets.encryption import seal, unseal
from harness.secrets.models import (
    MAX_SECRETS,
    Destination,
    SealedSecret,
    Secret,
    SecretNotFound,
    SecretRefused,
    SecretsFile,
    SecretSummary,
)

RECORD_ID_BYTES = 12
OWNER_ONLY = 0o600


class SecretService:
    """Every saved key, sealed in one file only this user can read."""

    def __init__(self, path: Path, *, encryption_key: str) -> None:
        if not encryption_key.strip():
            raise ValueError("the secrets encryption key must not be blank")
        self._path = path
        self._encryption_key = encryption_key

    def save(self, name: str, destination: Destination, value: SecretStr) -> None:
        """Seal `value` as the key `name`; one with the same destination is replaced."""
        stored = self._sealed_secrets()
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
        self._write((*(secret for secret in stored if secret is not existing), sealed))

    def find(self, name: str) -> Secret | None:
        """The key called `name`, unsealed, or `None` when none is saved."""
        sealed = next((s for s in self._sealed_secrets() if s.name == name), None)
        if sealed is None:
            return None
        plaintext = unseal(
            sealed.ciphertext, encryption_key=self._encryption_key, record_id=sealed.id
        )
        return Secret(destination=sealed.destination, value=SecretStr(plaintext))

    def delete(self, name: str) -> None:
        """Remove the key called `name`; `SecretNotFound` when none is saved."""
        stored = self._sealed_secrets()
        kept = tuple(secret for secret in stored if secret.name != name)
        if kept == stored:
            raise SecretNotFound(name)
        self._write(kept)

    def summaries(self) -> tuple[SecretSummary, ...]:
        """Every saved key's name and site, by name; never a value."""
        return tuple(
            SecretSummary(name=secret.name, destination=secret.destination)
            for secret in sorted(self._sealed_secrets(), key=lambda secret: secret.name)
        )

    def _sealed_secrets(self) -> tuple[SealedSecret, ...]:
        if not self._path.exists():
            return ()
        return SecretsFile.model_validate_json(self._path.read_text(encoding="utf-8")).secrets

    def _write(self, secrets: tuple[SealedSecret, ...]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        os.fchmod(handle, OWNER_ONLY)
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            file.write(SecretsFile(secrets=secrets).model_dump_json(indent=2))
        os.replace(temp, self._path)
