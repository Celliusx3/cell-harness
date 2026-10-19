"""A client tool is a declaration; the catalog turns it into a tool."""

from __future__ import annotations

from pydantic import BaseModel

from harness.tools.client.models import (
    DECLINED,
    UNAVAILABLE,
    ClientAnswer,
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

    def parse_answer(self, name: str, raw: object) -> ClientAnswer:
        """A posted body as the answer to the tool named `name`."""
        return self._by_name[name].answer_adapter().validate_python(raw)

    def outcome(self, answer: ClientAnswer) -> Ok | Failure:
        """What the model reads for an answer — the same for every datum."""
        if isinstance(answer, SharedAnswer):
            return Ok(content=answer.data.model_dump_json())
        if isinstance(answer, UnavailableAnswer):
            return Failure(
                UNAVAILABLE,
                f"the device could not answer ({answer.reason}); {_ASK_INSTEAD}",
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
