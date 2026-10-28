"""The keyring as the file keeps it: every saved key, sealed and bound to its record id."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from harness.secrets.models.details import CredentialDetails
from harness.secrets.models.secret import SecretName


class SealedSecret(BaseModel):
    """One saved key as the file holds it: sealed, and bound to its record id."""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    id: str = Field(pattern=r"^[0-9a-f]+$")
    name: SecretName
    details: CredentialDetails
    ciphertext: str

    @model_validator(mode="before")
    @classmethod
    def _custom_when_saved_before_kinds(cls, data: JsonValue) -> JsonValue:
        """An entry from before credentials had kinds holds a site, so it is a custom key."""
        if isinstance(data, dict) and "destination" in data and "details" not in data:
            kept = {key: value for key, value in data.items() if key != "destination"}
            return {**kept, "details": {"kind": "custom", "destination": data["destination"]}}
        return data


class SecretsFile(BaseModel):
    """The secrets file: the keyring, every saved key."""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    secrets: tuple[SealedSecret, ...] = ()
