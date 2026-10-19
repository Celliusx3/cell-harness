"""A saved key as the person types it, and as it is handed out: unsealed, or listed by name."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, SecretStr

from harness.secrets.models.destination import Destination

SecretName = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")]

SECRET_VALUE_RULE = "a key is 8 to 16384 printable ASCII characters, with no space at either end"

_TYPED_KEY = re.compile(r"[\x21-\x7e][\x20-\x7e]{6,16382}[\x21-\x7e]")


def _typeable_value(value: SecretStr) -> SecretStr:
    if _TYPED_KEY.fullmatch(value.get_secret_value()) is None:
        raise ValueError(SECRET_VALUE_RULE)
    return value


SecretValue = Annotated[SecretStr, AfterValidator(_typeable_value)]


class UnsealedSecret(BaseModel):
    """A saved key, unsealed, with the site it may be sent to."""

    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)

    destination: Destination
    value: SecretStr


class SecretSummary(BaseModel):
    """A saved key's name and site, with neither its value nor its ciphertext."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: SecretName
    destination: Destination
