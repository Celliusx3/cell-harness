"""The bots page's request and response bodies."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AllowedSecrets(BaseModel):
    """The names of the saved keys a bot may use, replacing the list it had."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    names: tuple[str, ...]
