"""The credentials page's request and response bodies."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator

from harness.secrets import SavedCredential, SecretName, SecretValue
from harness.secrets.models.details import ChatPlatformDetails, CredentialDetails, ModelDetails

PLATFORM_SERVES_NO_BOTS = "a Telegram or Discord credential serves no bots; tick none"
MODEL_PICKED_IN_EDIT_BOT = "a bot's model is picked in Edit bot; tick none"


class BotRef(BaseModel):
    """A bot a credential serves: its id and the name the sidebar shows."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    name: str


class CredentialEntry(SavedCredential):
    """One credential as the Credentials page lists it, with the bots it serves."""

    bots: tuple[BotRef, ...]


class CredentialList(BaseModel):
    """Every credential by name, and the address to save at."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    credentials: tuple[CredentialEntry, ...]
    direct_url: str


class NewCredential(BaseModel):
    """A credential typed into the dialog: its name, what it is for, its key, and its bots."""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    name: SecretName
    details: CredentialDetails
    value: SecretValue
    bot_ids: tuple[str, ...]

    @model_validator(mode="after")
    def _serves_bots_only_if_a_key_for_them(self) -> NewCredential:
        _refuse_bots_where_none_served(self.details, self.bot_ids)
        return self


class CredentialChange(BaseModel):
    """An edit from the dialog: what it is for, a new key or `None` to keep it, and its bots."""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    details: CredentialDetails
    value: SecretValue | None
    bot_ids: tuple[str, ...]

    @model_validator(mode="after")
    def _serves_bots_only_if_a_key_for_them(self) -> CredentialChange:
        _refuse_bots_where_none_served(self.details, self.bot_ids)
        return self


def _refuse_bots_where_none_served(details: CredentialDetails, bot_ids: tuple[str, ...]) -> None:
    if not bot_ids:
        return
    if isinstance(details, ChatPlatformDetails):
        raise ValueError(PLATFORM_SERVES_NO_BOTS)
    if isinstance(details, ModelDetails):
        raise ValueError(MODEL_PICKED_IN_EDIT_BOT)
