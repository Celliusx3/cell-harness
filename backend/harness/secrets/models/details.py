"""What a credential is for beside its key: a site, a model, a chat platform, or a capability."""

from __future__ import annotations

from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from harness.secrets.models.destination import Destination

THIS_COMPUTER = frozenset({"localhost", "127.0.0.1", "::1"})


class CustomDetails(BaseModel):
    """A key a bot sends to one website, as the Keys page saved them."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["custom"] = "custom"
    destination: Destination


class ModelDetails(BaseModel):
    """A model provider's endpoint, the model to ask there, and whether it can see images."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["llm"] = "llm"
    base_url: str
    model: str
    vision: bool

    @field_validator("base_url")
    @classmethod
    def _web_endpoint(cls, value: str) -> str:
        parts = urlsplit(value)
        if not parts.hostname:
            raise ValueError("the endpoint must be an https:// address")
        if parts.scheme == "https":
            return value
        if parts.scheme == "http" and parts.hostname in THIS_COMPUTER:
            return value
        raise ValueError(
            "the endpoint must be an https:// address; plain http:// is only for "
            "localhost or 127.0.0.1"
        )

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


class CapabilityDetails(BaseModel):
    """One env variable of one MCP server, by the server's id; the key is the sealed value."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["capability"] = "capability"
    server: str
    variable: str

    @field_validator("server", "variable")
    @classmethod
    def _named(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("a capability key names its server and its env variable")
        return value


ChatPlatform = Literal["telegram", "discord"]

ChatPlatformDetails = TelegramDetails | DiscordDetails

CredentialDetails = Annotated[
    CustomDetails | ModelDetails | TelegramDetails | DiscordDetails | CapabilityDetails,
    Field(discriminator="kind"),
]
