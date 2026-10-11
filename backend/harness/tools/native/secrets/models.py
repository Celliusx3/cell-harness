"""What the two secrets tools are called with, and the name `ask_for_secret` hands back."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from harness.secrets import Destination, SecretName


class SecretAsk(Destination):
    """The key to ask for: its name, its site, how the site takes it, and the card's label."""

    name: SecretName = Field(
        description="The key's name: lowercase letters, digits and underscores."
    )
    label: str = Field(min_length=1, max_length=80, description="What the card calls the key.")

    @property
    def destination(self) -> Destination:
        """Where and how the key may be sent, without its name or the card's label."""
        return Destination(origin=self.origin, auth=self.auth, header_name=self.header_name)


class SavedName(BaseModel):
    """The name the key was saved under — all the model ever gets back."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str


class FetchArgs(BaseModel):
    """One request: which saved key, where, how, and an optional JSON body."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(description="The name the key was saved under.")
    url: str = Field(description="An https url on the origin the key was saved for.")
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    body: JsonValue = Field(default=None, description="JSON to send. Leave it out for GET.")
