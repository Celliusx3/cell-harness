"""A client tool is a declaration; the catalog turns it into a tool."""

from __future__ import annotations

from pydantic import BaseModel

from harness.tools.client.models import (
    DECLINED,
    UNAVAILABLE,
    ClientOutput,
    ClientTool,
    SharedAnswer,
    UnavailableAnswer,
)
from harness.tools.models.context import ToolContext
from harness.tools.models.outcome import Failure, Ok, Pending, ToolOutcome
from harness.tools.models.tool import Tool

_ASK_INSTEAD = "ask them in words instead"


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
        if isinstance(output, SharedAnswer):
            return Ok(content=output.data.model_dump_json())
        if isinstance(output, UnavailableAnswer):
            return Failure(
                UNAVAILABLE,
                f"the device could not answer ({output.reason}); {_ASK_INSTEAD}",
            )
        return Failure(DECLINED, f"the user chose not to answer; {_ASK_INSTEAD}")

    def tools(self) -> list[Tool]:
        """One registered tool per declaration. Each says only `Pending`."""
        return [_tool_for(declared) for declared in self._by_name.values()]


def _tool_for(declared: ClientTool) -> Tool:
    async def execute(_args: BaseModel, _context: ToolContext) -> ToolOutcome:
        return Pending()

    return Tool.from_model(
        name=declared.name,
        description=declared.description,
        args_model=declared.args_model,
        execute=execute,
    )
