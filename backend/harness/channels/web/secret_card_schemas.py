"""What the secret card sends: the key typed on it, and an LLM card's details."""

from __future__ import annotations

from typing import NamedTuple

from pydantic import BaseModel, ConfigDict, SecretStr

from harness.secrets import SecretValue
from harness.secrets.models.details import ModelDetails
from harness.tools.native.secrets.models import AskedDetails


class SecretEntry(BaseModel):
    """The key the person typed on the card."""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    value: SecretValue


class ModelEntry(BaseModel):
    """The key typed on an LLM card, with the endpoint, model and vision as the person left them."""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    value: SecretValue
    details: ModelDetails


class Entered(NamedTuple):
    """What the card saves: what the key is for, and the key."""

    details: AskedDetails
    value: SecretStr
