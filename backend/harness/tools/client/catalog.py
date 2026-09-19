"""A client tool is a declaration; the catalog turns it into a tool."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from harness.tools.context import ToolContext
from harness.tools.definition import Failure, Ok, Pending, ToolDefinition, ToolOutcome

DECLINED = "DECLINED"
UNAVAILABLE = "UNAVAILABLE"

_ASK_INSTEAD = "ask them in words instead"


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
    """One datum the client can provide — everything a new one has to say."""

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


class ClientTools:
    """Every declared client tool: parsed, resolved to an outcome, and defined."""

    def __init__(self, tools: tuple[ClientTool, ...]) -> None:
        self._by_name = {tool.name: tool for tool in tools}
        if len(self._by_name) != len(tools):
            raise ValueError("two client tools share a name")

    @property
    def names(self) -> frozenset[str]:
        return frozenset(self._by_name)

    def parse(self, name: str, raw: object) -> ClientOutput:
        """A posted body as the output of the tool named `name`."""
        return self._by_name[name].output_adapter().validate_python(raw)

    def outcome(self, output: ClientOutput) -> Ok | Failure:
        """What the model reads for an answer — the same for every datum."""
        if isinstance(output, Shared):
            return Ok(content=output.data.model_dump_json())
        if isinstance(output, Unavailable):
            return Failure(
                UNAVAILABLE,
                f"the device could not answer ({output.reason}); {_ASK_INSTEAD}",
            )
        return Failure(DECLINED, f"the user chose not to answer; {_ASK_INSTEAD}")

    def definitions(self) -> list[ToolDefinition]:
        """One registered tool per declaration. Each says only `Pending`."""
        return [_definition(tool) for tool in self._by_name.values()]


def _definition(tool: ClientTool) -> ToolDefinition:
    async def execute(_args: BaseModel, _context: ToolContext) -> ToolOutcome:
        return Pending()

    return ToolDefinition.from_model(
        name=tool.name, description=tool.description, args_model=tool.args_model, execute=execute
    )
