"""What a client tool declares, what a client answers, and what comes of a waiting call."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from harness.tools.models.decision import Approved
from harness.tools.models.outcome import Failure, Ok

DECLINED = "DECLINED"
UNAVAILABLE = "UNAVAILABLE"


class Shared[DataT: BaseModel](BaseModel):
    """The client answered with the datum."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["shared"] = "shared"
    data: DataT


class Declined(BaseModel):
    """The person chose not to."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["declined"] = "declined"


class Unavailable(BaseModel):
    """The device could not — permission blocked, no fix, timed out."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["unavailable"] = "unavailable"
    reason: str = Field(min_length=1)


ClientOutput = Shared[BaseModel] | Declined | Unavailable


@dataclass(frozen=True)
class ClientTool[ArgsT: BaseModel, DataT: BaseModel]:
    """One datum the client can provide."""

    name: str
    description: str
    args_model: type[ArgsT]
    data_model: type[DataT]

    def output_adapter(self) -> TypeAdapter[ClientOutput]:
        """The union a posted body must fit, with this tool's data inside."""
        return TypeAdapter(
            Annotated[
                Shared[self.data_model] | Declined | Unavailable,  # type: ignore[valid-type]
                Field(discriminator="kind"),
            ]
        )


@dataclass(frozen=True)
class PendingCall:
    """One call the client answers, with no result yet."""

    name: str
    call_id: str
    arguments: str


class Refused(Enum):
    """Why an answer was not taken."""

    NOT_PENDING = "not_pending"
    DOES_NOT_FIT = "does_not_fit"


@dataclass(frozen=True)
class Accepted:
    """An answer that fits: what the resumed turn opens with."""

    call_id: str
    outcome: Ok | Failure | Approved
