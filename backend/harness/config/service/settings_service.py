"""Settings for a real run: what cannot be left to a default is checked."""

from __future__ import annotations

import shutil

from harness.config.repository.settings_repository import Settings, SettingsRepository


class MissingConfigError(RuntimeError):
    """A value with no possible default was not supplied anywhere."""


class SettingsService:
    """The settings a real run starts with, refused when Deno or the encryption key is missing."""

    def __init__(self, repository: SettingsRepository) -> None:
        self._repository = repository

    def load(self) -> Settings:
        """Settings for a real run, with Deno and the encryption key checked."""
        settings = self._repository.read()
        self._require_deno(settings)
        self._require_encryption_key(settings)
        return settings

    def _require_deno(self, settings: Settings) -> None:
        if shutil.which(settings.code.deno_path) is None:
            raise MissingConfigError(
                f"{settings.code.deno_path!r} is not on PATH, and the harness runs "
                "every tool call through a Deno sandbox. Install Deno "
                f"(https://deno.com) or set code.deno_path in {self._repository.committed_path}."
            )

    def _require_encryption_key(self, settings: Settings) -> None:
        if not settings.secrets.encryption_key.strip():
            raise MissingConfigError(
                f"secrets.encryption_key is not set. It belongs in {self._repository.local_path} "
                '(gitignored) as {"secrets": {"encryption_key": "…"}}, or in '
                "HARNESS_SECRETS__ENCRYPTION_KEY. Make one with `openssl rand -hex 32`. "
                "Changing it makes every saved key unreadable."
            )
