"""A client tool is a declaration; the catalog turns it into a tool.

`ClientTool` says what a datum *is* — name, description, what the model
passes, what a shared answer carries. What a client can answer with is the
same for every datum (`ClientOutput`), and what the model reads is decided
here, once: shared data as JSON, the way every MCP tool already answers; a
refusal and an inability as two typed failures, because the model recovers
the same way from each but the guardrail counts by code and the card reads
it. A tool that *does* something on the device rather than reading it —
Claude's share sheet, "add to calendar" — is the same shape with an empty
`data_model`.

The tool itself does nothing but say `Pending`: the loop ends the turn there,
and the answer opens a later one (`LoopAgent.resume`). Nothing waits.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from harness.tools.context import ToolContext
from harness.tools.definition import Failure, Ok, Pending, ToolDefinition, ToolOutcome

# Two codes, because the model recovers differently from each and the
# guardrail counts by code. "The person said no" is kept apart from "the
# device could not" on purpose: a client that silently declines what it could
# not ask is the failure the prior art warns about. (A third, `SKIPPED`, is
# the loop's — written when the person moves on without answering.)
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
    """The device could not — permission blocked, no fix, timed out. Distinct
    from declining: nobody said no. `reason` is the platform's own code
    (a browser's `PERMISSION_DENIED`), forwarded rather than translated."""

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
    """Every declared client tool, and the two things done with them all."""

    def __init__(self, tools: tuple[ClientTool, ...]) -> None:
        self._by_name = {tool.name: tool for tool in tools}
        if len(self._by_name) != len(tools):
            raise ValueError("two client tools share a name")

    @property
    def names(self) -> frozenset[str]:
        return frozenset(self._by_name)

    def parse(self, name: str, raw: object) -> ClientOutput:
        """A posted body as the output of the tool named `name`.

        Raises `ValidationError` for a body that does not fit, and
        `KeyError` for a name that is not a client tool — a caller has
        already matched `name` against `pending_call`, so that is a bug.
        """
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
