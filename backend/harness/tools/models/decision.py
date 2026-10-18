"""The person's answer to a call that asks before it runs."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

DENIED = "DENIED"

Scope = Literal["once", "conversation", "always"]


class Approved(BaseModel):
    """The person let the call run, for this call, this conversation, or always."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["approved"] = "approved"
    scope: Scope


class Denied(BaseModel):
    """The person refused the call."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["denied"] = "denied"


Decision = Approved | Denied

_DECISION_ADAPTER = TypeAdapter(Annotated[Decision, Field(discriminator="kind")])


def parse_decision(raw: object) -> Decision:
    """A posted body as the person's decision; `ValidationError` when it is not one."""
    return _DECISION_ADAPTER.validate_python(raw)
