"""The keyring on disk: one JSON file of sealed keys, readable by its owner alone."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from harness.secrets.models.sealed import SealedSecret, SecretsFile

OWNER_ONLY = 0o600


@dataclass(frozen=True)
class DiskSecretRepository:
    """The keyring as one file at `path`, replaced whole and readable by its owner alone."""

    path: Path

    def sealed_secrets(self) -> tuple[SealedSecret, ...]:
        """Every saved key, sealed; `()` when there is no file."""
        if not self.path.exists():
            return ()
        return SecretsFile.model_validate_json(self.path.read_text(encoding="utf-8")).secrets

    def replace_all(self, secrets: tuple[SealedSecret, ...]) -> None:
        """The keyring replaced whole by `secrets`, its folder made when missing."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        os.fchmod(handle, OWNER_ONLY)
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            file.write(SecretsFile(secrets=secrets).model_dump_json(indent=2))
        os.replace(temp, self.path)
