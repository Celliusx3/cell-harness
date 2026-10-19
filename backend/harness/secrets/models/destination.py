"""Where a saved key may be sent: the one https origin, and how that API takes the key."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SecretAuth = Literal["bearer", "header"]

_ORIGIN = re.compile(r"https://[A-Za-z0-9.-]+(?::(?P<port>\d{1,5}))?")
_HEADER_TOKEN = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+")
_RESERVED_HEADERS = frozenset(
    {"host", "content-length", "transfer-encoding", "connection", "cookie"}
)


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
