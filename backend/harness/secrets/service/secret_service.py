"""The keyring's rules, held over its repository: one site per name, a cap, each key sealed."""

from __future__ import annotations

import os

from pydantic import SecretStr

from harness.secrets.domain.destination import Destination
from harness.secrets.domain.details import (
    ChatPlatform,
    ChatPlatformDetails,
    CredentialDetails,
    CustomDetails,
    ModelDetails,
)
from harness.secrets.domain.errors import SecretNotFound, SecretRefused
from harness.secrets.domain.masking import last_four
from harness.secrets.domain.sealed import SealedSecret
from harness.secrets.domain.secret import (
    SavedCredential,
    SecretSummary,
    UnsealedModelCredential,
    UnsealedSecret,
)
from harness.secrets.repository.secret_repository import SecretRepository
from harness.secrets.service.sealing import sealed, unsealed

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
        if existing is not None and not isinstance(existing.details, CustomDetails):
            raise SecretRefused(
                f"a {existing.details.kind} credential is already named {name!r}; pick another name"
            )
        if existing is not None and existing.details.destination != destination:
            raise SecretRefused(
                f"a key named {name!r} is already saved for {existing.details.destination.origin}; "
                "remove it before saving it for another site"
            )
        if existing is None and len(stored) >= MAX_SECRETS:
            raise SecretRefused(f"{MAX_SECRETS} keys are already saved; remove one first")
        record_id = os.urandom(RECORD_ID_BYTES).hex()
        sealed_secret = SealedSecret(
            id=record_id,
            name=name,
            details=CustomDetails(destination=destination),
            ciphertext=sealed(
                value.get_secret_value(),
                encryption_key=self._encryption_key,
                record_id=record_id,
            ),
        )
        self._repository.replace_all(
            (*(secret for secret in stored if secret is not existing), sealed_secret)
        )

    def add_credential(self, name: str, details: CredentialDetails, value: SecretStr) -> None:
        """Seal `value` as a new credential; refused for a name taken, or a platform saved twice."""
        stored = self._repository.sealed_secrets()
        if any(secret.name == name for secret in stored):
            raise SecretRefused(f"a credential is already named {name!r}; pick another name")
        if isinstance(details, ChatPlatformDetails):
            _refuse_a_second(stored, details.kind)
        if len(stored) >= MAX_SECRETS:
            raise SecretRefused(f"{MAX_SECRETS} keys are already saved; remove one first")
        added = self._sealed_secret(name, details, value.get_secret_value())
        self._repository.replace_all((*stored, added))

    def change_credential(
        self, name: str, details: CredentialDetails, value: SecretStr | None
    ) -> CredentialDetails:
        """Replace what `name` is for, and its key unless `value` is `None`; say what it was for."""
        stored = self._repository.sealed_secrets()
        existing = next((secret for secret in stored if secret.name == name), None)
        if existing is None:
            raise SecretNotFound(name)
        if existing.details.kind != details.kind:
            raise SecretRefused(
                f"{name!r} is a {existing.details.kind} credential; its type cannot change"
            )
        plaintext = self._plaintext(existing) if value is None else value.get_secret_value()
        changed = self._sealed_secret(name, details, plaintext)
        self._repository.replace_all(
            tuple(changed if secret is existing else secret for secret in stored)
        )
        return existing.details

    def secret_named(self, name: str) -> UnsealedSecret | None:
        """The custom key called `name`, unsealed, or `None`; no other kind is ever handed out."""
        sealed_secret = next((s for s in self._repository.sealed_secrets() if s.name == name), None)
        if sealed_secret is None or not isinstance(sealed_secret.details, CustomDetails):
            return None
        plaintext = unsealed(
            sealed_secret.ciphertext,
            encryption_key=self._encryption_key,
            record_id=sealed_secret.id,
        )
        return UnsealedSecret(
            destination=sealed_secret.details.destination, value=SecretStr(plaintext)
        )

    def details_of(self, name: str) -> CredentialDetails | None:
        """What the credential `name` is for, of any kind, or `None`; its key stays sealed."""
        sealed_secret = self._sealed_named(name)
        return None if sealed_secret is None else sealed_secret.details

    def model_credential_version(self, name: str) -> str | None:
        """The record id the LLM credential `name` is sealed under, new on every save, or `None`."""
        sealed_secret = self._sealed_named(name)
        if sealed_secret is None or not isinstance(sealed_secret.details, ModelDetails):
            return None
        return sealed_secret.id

    def not_a_model_reason(self, name: str) -> str | None:
        """Why `name` cannot be a bot's model, naming the saved LLM credentials; or `None`."""
        if self.model_credential_version(name) is not None:
            return None
        saved = self.model_credential_names()
        listed = f"the saved ones are {', '.join(saved)}" if saved else "none is saved"
        return f"{name!r} is not a saved LLM credential; {listed}"

    def model_credential_names(self) -> tuple[str, ...]:
        """The saved LLM credentials' names, in the order they were saved."""
        return tuple(
            secret.name
            for secret in self._repository.sealed_secrets()
            if isinstance(secret.details, ModelDetails)
        )

    def model_credential_named(self, name: str) -> UnsealedModelCredential | None:
        """The LLM credential called `name`, unsealed, or `None`; no other kind is handed out."""
        sealed_secret = self._sealed_named(name)
        if sealed_secret is None or not isinstance(sealed_secret.details, ModelDetails):
            return None
        return UnsealedModelCredential(
            details=sealed_secret.details, key=SecretStr(self._plaintext(sealed_secret))
        )

    def chat_platform_token(self, platform: ChatPlatform) -> SecretStr | None:
        """The Telegram or Discord credential's token, unsealed, or `None`; no other kind."""
        sealed_secret = _platform_credential(self._repository.sealed_secrets(), platform)
        return None if sealed_secret is None else SecretStr(self._plaintext(sealed_secret))

    def delete(self, name: str) -> CredentialDetails:
        """Remove the key called `name` and say what it was for."""
        stored = self._repository.sealed_secrets()
        removed = next((secret for secret in stored if secret.name == name), None)
        if removed is None:
            raise SecretNotFound(name)
        self._repository.replace_all(tuple(secret for secret in stored if secret is not removed))
        return removed.details

    def summaries(self) -> tuple[SecretSummary, ...]:
        """Every custom key's name and site, by name; never a value."""
        return tuple(
            SecretSummary(name=secret.name, destination=secret.details.destination)
            for secret in sorted(self._repository.sealed_secrets(), key=lambda secret: secret.name)
            if isinstance(secret.details, CustomDetails)
        )

    def saved_credentials(self) -> tuple[SavedCredential, ...]:
        """Every credential of every kind, by name, with its last four characters at most."""
        return tuple(
            self._saved_credential(secret)
            for secret in sorted(self._repository.sealed_secrets(), key=lambda secret: secret.name)
        )

    def _sealed_named(self, name: str) -> SealedSecret | None:
        return next((s for s in self._repository.sealed_secrets() if s.name == name), None)

    def _sealed_secret(self, name: str, details: CredentialDetails, plaintext: str) -> SealedSecret:
        record_id = os.urandom(RECORD_ID_BYTES).hex()
        return SealedSecret(
            id=record_id,
            name=name,
            details=details,
            ciphertext=sealed(plaintext, encryption_key=self._encryption_key, record_id=record_id),
        )

    def _saved_credential(self, secret: SealedSecret) -> SavedCredential:
        return SavedCredential(
            name=secret.name,
            details=secret.details,
            last_four=last_four(self._plaintext(secret)),
        )

    def _plaintext(self, secret: SealedSecret) -> str:
        return unsealed(secret.ciphertext, encryption_key=self._encryption_key, record_id=secret.id)


def _platform_credential(
    stored: tuple[SealedSecret, ...], platform: ChatPlatform
) -> SealedSecret | None:
    """The one credential for `platform` in `stored`, whatever its name, or `None`."""
    return next(
        (
            secret
            for secret in stored
            if isinstance(secret.details, ChatPlatformDetails) and secret.details.kind == platform
        ),
        None,
    )


def _refuse_a_second(stored: tuple[SealedSecret, ...], platform: ChatPlatform) -> None:
    """`SecretRefused` when `stored` already holds `platform`'s one credential."""
    saved = _platform_credential(stored, platform)
    if saved is not None:
        raise SecretRefused(
            f"the {platform} credential is already saved as {saved.name!r}; "
            "there is one per platform, so edit or remove it"
        )
