"""The keyring as the file keeps it: every saved key, sealed and bound to its record id."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from harness.secrets.models.destination import Destination
from harness.secrets.models.secret import SecretName


class SealedSecret(BaseModel):
    """One saved key as the file holds it: sealed, and bound to its record id."""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    id: str = Field(pattern=r"^[0-9a-f]+$")
    name: SecretName
    destination: Destination
    ciphertext: str


class SecretsFile(BaseModel):
    """The secrets file: the keyring, every saved key."""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    secrets: tuple[SealedSecret, ...] = ()
