"""Where a saved key may be sent, how it is stored, and what the person may type as one."""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

SecretAuth = Literal["bearer", "header"]
SecretName = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")]

SECRET_VALUE_RULE = "a key is 8 to 16384 printable ASCII characters, with no space at either end"

_TYPED_KEY = re.compile(r"[\x21-\x7e][\x20-\x7e]{6,16382}[\x21-\x7e]")
_ORIGIN = re.compile(r"https://[A-Za-z0-9.-]+(?::(?P<port>\d{1,5}))?")
_HEADER_TOKEN = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+")
_RESERVED_HEADERS = frozenset(
    {"host", "content-length", "transfer-encoding", "connection", "cookie"}
)


def _typeable(value: SecretStr) -> SecretStr:
    if _TYPED_KEY.fullmatch(value.get_secret_value()) is None:
        raise ValueError(SECRET_VALUE_RULE)
    return value


SecretValue = Annotated[SecretStr, AfterValidator(_typeable)]


class Destination(BaseModel):
    """The one https origin a key may be sent to, and how that API expects it."""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    origin: str = Field(
        description="The exact https origin of the API that receives the key, with no path."
    )
    auth: SecretAuth = Field(
        description=(
            "How the API takes the key: bearer sends Authorization: Bearer <key>; "
            "header sends it in header_name."
        )
    )
    header_name: str | None = Field(
        default=None, description="The header that carries the key, when auth is header."
    )

    @field_validator("origin")
    @classmethod
    def _bare_https_origin(cls, value: str) -> str:
        match = _ORIGIN.fullmatch(value)
        if match is None or not 0 < int(match["port"] or 443) <= 65535:
            raise ValueError(
                "must be an https origin and nothing more, like https://api.example.com"
            )
        return value

    @field_validator("header_name")
    @classmethod
    def _sendable_header(cls, value: str | None) -> str | None:
        if value is not None and _HEADER_TOKEN.fullmatch(value) is None:
            raise ValueError("must be an HTTP header name, like X-Api-Key")
        if value is not None and value.lower() in _RESERVED_HEADERS:
            raise ValueError(f"cannot be one of {', '.join(sorted(_RESERVED_HEADERS))}")
        return value

    @model_validator(mode="after")
    def _header_name_fits_auth(self) -> Destination:
        if self.auth == "header" and self.header_name is None:
            raise ValueError('header_name is required when auth is "header"')
        if self.auth == "bearer" and self.header_name is not None:
            raise ValueError('header_name is only for auth "header"; "bearer" uses Authorization')
        return self


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


class Secret(BaseModel):
    """A saved key, unsealed, with the site it may be sent to."""

    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)

    destination: Destination
    value: SecretStr


class SecretSummary(BaseModel):
    """A saved key's name and site, with neither its value nor its ciphertext."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: SecretName
    destination: Destination


class SecretRefused(ValueError):
    """A key that cannot be saved; the message never holds the key."""


class SecretNotFound(LookupError):
    """No key is saved under that name."""

    def __init__(self, name: str) -> None:
        super().__init__(f"no saved key named {name!r}")
