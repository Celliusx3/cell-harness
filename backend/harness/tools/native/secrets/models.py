"""What the two secrets tools are called with, and the name `ask_for_secret` hands back."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError, model_validator

from harness.secrets import Destination, SecretName
from harness.secrets.models.destination import SecretAuth
from harness.secrets.models.details import (
    CustomDetails,
    DiscordDetails,
    ModelDetails,
    TelegramDetails,
)

AskedKind = Literal["custom", "llm", "telegram", "discord"]

AskedDetails = CustomDetails | ModelDetails | TelegramDetails | DiscordDetails

CUSTOM_FIELDS = ("origin", "auth", "header_name")
LLM_FIELDS = ("base_url", "model", "vision")


class SecretAsk(BaseModel):
    """The key to ask for: what it is for, its name, the card's label, and that kind's fields."""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    kind: AskedKind = Field(
        description=(
            "custom: a key for one website's API. llm: a key for a model provider. "
            "telegram or discord: the token of the app's own chat bot there."
        )
    )
    name: SecretName = Field(
        description="The key's name: lowercase letters, digits and underscores."
    )
    label: str = Field(min_length=1, max_length=80, description="What the card calls the key.")
    origin: str | None = Field(
        default=None,
        description="custom: the exact https origin of the API that receives the key, no path.",
    )
    auth: SecretAuth | None = Field(
        default=None,
        description=(
            "custom: how the API takes the key: bearer sends Authorization: Bearer <key>; "
            "header sends it in header_name."
        ),
    )
    header_name: str | None = Field(
        default=None, description="custom: the header that carries the key, when auth is header."
    )
    base_url: str | None = Field(
        default=None, description="llm: the provider's OpenAI-compatible https endpoint."
    )
    model: str | None = Field(default=None, description="llm: the model's name at base_url.")
    vision: bool | None = Field(default=None, description="llm: whether the model sees images.")

    @model_validator(mode="after")
    def _fields_fit_kind(self) -> SecretAsk:
        try:
            _asked_details(self)
        except ValidationError as err:
            raise ValueError(_reasons(err)) from None
        return self

    @property
    def details(self) -> AskedDetails:
        """What the key is for, as the card shows it before the person edits it."""
        return _asked_details(self)


def _asked_details(ask: SecretAsk) -> AskedDetails:
    if ask.kind == "custom":
        _refuse_fields_of_another_kind(ask, LLM_FIELDS)
        if ask.origin is None or ask.auth is None:
            raise ValueError('origin and auth are required when kind is "custom"')
        return CustomDetails(
            destination=Destination(origin=ask.origin, auth=ask.auth, header_name=ask.header_name)
        )
    _refuse_fields_of_another_kind(ask, CUSTOM_FIELDS)
    if ask.kind == "llm":
        if ask.base_url is None or ask.model is None or ask.vision is None:
            raise ValueError('base_url, model and vision are required when kind is "llm"')
        return ModelDetails(base_url=ask.base_url, model=ask.model, vision=ask.vision)
    _refuse_fields_of_another_kind(ask, LLM_FIELDS)
    return TelegramDetails() if ask.kind == "telegram" else DiscordDetails()


def _refuse_fields_of_another_kind(ask: SecretAsk, fields: tuple[str, ...]) -> None:
    sent = [field for field in fields if getattr(ask, field) is not None]
    if sent:
        raise ValueError(f"leave out {', '.join(sent)}; kind {ask.kind!r} does not take them")


def _reasons(err: ValidationError) -> str:
    return "; ".join(
        str(error["msg"]).removeprefix("Value error, ")
        for error in err.errors(include_url=False, include_input=False)
    )


class SavedName(BaseModel):
    """The name the key was saved under, and what it is for — all the model ever gets back."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    kind: AskedKind


class FetchArgs(BaseModel):
    """One request: which saved key, where, how, and an optional JSON body."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(description="The name the key was saved under.")
    url: str = Field(description="An https url on the origin the key was saved for.")
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    body: JsonValue = Field(default=None, description="JSON to send. Leave it out for GET.")
