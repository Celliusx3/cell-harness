"""What a credential is for beside its sealed value: a site, a model, or a chat platform."""

from __future__ import annotations

from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from harness.secrets.models.destination import Destination

WEB_SCHEMES = frozenset({"http", "https"})


class CustomDetails(BaseModel):
    """A key a bot sends to one website, as the Keys page saved them."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["custom"] = "custom"
    destination: Destination


class ModelDetails(BaseModel):
    """A model provider's endpoint and the model to ask there; the key is the sealed value."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["llm"] = "llm"
    base_url: str
    model: str

    @field_validator("base_url")
    @classmethod
    def _web_endpoint(cls, value: str) -> str:
        parts = urlsplit(value)
        if parts.scheme not in WEB_SCHEMES or not parts.netloc:
            raise ValueError("the endpoint must be an http:// or https:// address")
        return value

    @field_validator("model")
    @classmethod
    def _named_model(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("the model must be named")
        return value


class TelegramDetails(BaseModel):
    """The app's Telegram bot; the token is the sealed value."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["telegram"] = "telegram"


class DiscordDetails(BaseModel):
    """The app's Discord bot; the token is the sealed value."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["discord"] = "discord"


ChatPlatform = Literal["telegram", "discord"]

ChatPlatformDetails = TelegramDetails | DiscordDetails

CredentialDetails = Annotated[
    CustomDetails | ModelDetails | TelegramDetails | DiscordDetails,
    Field(discriminator="kind"),
]
