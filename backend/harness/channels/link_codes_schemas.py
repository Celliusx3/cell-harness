"""A link-code request, and the code issued for it."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from harness.secrets.models.details import ChatPlatform


class LinkCodeRequest(BaseModel):
    """The platform whose direct chat the code is for."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    platform: ChatPlatform


class IssuedLinkCode(BaseModel):
    """A code, the seconds it lasts, and the name of the bot it links to."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    expires_in_seconds: int
    bot_name: str
