"""What a tool is, and how a call's arguments are checked before it runs."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from harness.llm import ToolSpec
from harness.tools.models.context import ToolContext
from harness.tools.models.outcome import EXECUTION_ERROR, INVALID_ARGUMENTS, Failure, ToolOutcome

NAMESPACE = "__"


@dataclass(frozen=True)
class ToolDefinition[ArgsT]:
    """One tool the model can call."""

    name: str
    description: str
    input_schema: dict
    parse: Callable[[dict], ArgsT]
    execute: Callable[[ArgsT, ToolContext], Awaitable[ToolOutcome]]

    @classmethod
    def from_model[M: BaseModel](
        cls,
        *,
        name: str,
        description: str,
        args_model: type[M],
        execute: Callable[[M, ToolContext], Awaitable[ToolOutcome]],
    ) -> ToolDefinition[M]:
        """A tool whose code we own, described by one Pydantic model."""
        return ToolDefinition(
            name=name,
            description=description,
            input_schema=args_model.model_json_schema(),
            parse=args_model.model_validate,
            execute=execute,
        )

    def spec(self) -> ToolSpec:
        """The declaration handed to the model — **an allowlist**."""
        return ToolSpec(
            name=self.name,
            description=self.description,
            input_schema=self.input_schema,
        )

    def _missing_required_message(self, raw: dict) -> str | None:
        """A required field the model left out, or `None`."""
        required = [f for f in self.input_schema.get("required", ()) if f not in raw]
        if not required:
            return None
        fields = self.input_schema.get("properties", {})
        expected = ", ".join(
            f"{name} (required)" if name in self.input_schema.get("required", ()) else name
            for name in fields
        )
        return (
            f"invalid arguments for {self.name!r}: missing required field "
            f"{', '.join(required)}. You sent: {', '.join(raw) or 'nothing'}. "
            f"Expected fields: {expected}."
        )

    async def invoke(self, arguments: str, *, context: ToolContext) -> ToolOutcome:
        """Parse the model's raw argument string, then run."""
        try:
            raw = json.loads(arguments) if arguments.strip() else {}
        except json.JSONDecodeError as err:
            return Failure(
                INVALID_ARGUMENTS, f"arguments for {self.name!r} are not valid JSON: {err}"
            )
        if not isinstance(raw, dict):
            return Failure(
                INVALID_ARGUMENTS,
                f"arguments for {self.name!r} must be a JSON object, got {type(raw).__name__}",
            )

        if missing := self._missing_required_message(raw):
            return Failure(INVALID_ARGUMENTS, missing)

        try:
            parsed = self.parse(raw)
        except ValidationError as err:
            return Failure(INVALID_ARGUMENTS, f"invalid arguments for {self.name!r}: {err}")

        try:
            return await self.execute(parsed, context)
        except Exception as err:
            return Failure(EXECUTION_ERROR, f"{self.name} failed: {type(err).__name__}: {err}")
