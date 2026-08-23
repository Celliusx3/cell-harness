"""What a tool is, and what it returns.

Two ideas carry most of the weight here.

**The outcome is typed.** `Ok | Failure` rather than a string that starts with
`"error: "`. The model still sees the string — `render_outcome` produces it, and
a tolerant string is what lets the model recover instead of the turn dying — but
everything *inside* the harness switches on the type. The guardrail in phase 8
counts failures by `Failure.code`; keying it on a string prefix would make any
tool that phrased its error differently invisible to the detectors, which is the
one fragility in cell-bot's otherwise identical design.

**The schema and the parser come from one model.** `from_model` derives both
from a single Pydantic class, so what the model is told and what the executor
accepts cannot drift. Build a `ToolDefinition` directly only when the schema
comes from somewhere we do not control — an MCP server publishes its own, and
validating against our copy would silently drop arguments that server accepts.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from harness.llm.messages import ToolSpec
from harness.tools.progress import ToolProgressReporter

# Failure codes. Stable identifiers the guardrail and UI switch on, distinct from
# the human-readable message beside them.
INVALID_ARGUMENTS = "INVALID_ARGUMENTS"
UNKNOWN_TOOL = "UNKNOWN_TOOL"
EXECUTION_ERROR = "EXECUTION_ERROR"

# The prefix every tolerant failure wears on the wire. One constant, because the
# model learns this shape and a second spelling would read as a different kind of
# thing.
ERROR_PREFIX = "error: "


@dataclass(frozen=True)
class Ok:
    """A call that produced a result.

    Phase 4 adds tool-private presentation data here (a diff, a row count) once
    there is a UI to render a card from it.
    """

    content: str


@dataclass(frozen=True)
class Failure:
    """A call that did not.

    Not an exception: an unknown tool, bad arguments, or a tool that raised are
    all ordinary traffic the model can recover from on the next step. Exceptions
    are reserved for our own bugs.
    """

    code: str
    message: str


ToolOutcome = Ok | Failure


def render_outcome(outcome: ToolOutcome) -> str:
    """What the model sees.

    The only place the wire format is decided, so a `Failure` cannot reach the
    model wearing two different shapes.
    """
    if isinstance(outcome, Ok):
        return outcome.content
    return f"{ERROR_PREFIX}{outcome.message}"


@dataclass(frozen=True)
class ToolDefinition[ArgsT]:
    """One tool the model can call.

    `ArgsT` is whatever `parse` produces and `execute` consumes: a Pydantic model
    for a tool whose code we own, so the executor gets typed and coerced values;
    or a plain `dict` for one that forwards its arguments somewhere else
    untouched.
    """

    name: str
    description: str
    # What the model is told. Explicit rather than derived, because a remote
    # tool's schema is published by its server and we are only relaying it.
    input_schema: dict
    # Raw argument dict -> what the executor wants.
    parse: Callable[[dict], ArgsT]
    execute: Callable[[ArgsT, ToolProgressReporter], Awaitable[ToolOutcome]]

    @classmethod
    def from_model[M: BaseModel](
        cls,
        *,
        name: str,
        description: str,
        args_model: type[M],
        execute: Callable[[M, ToolProgressReporter], Awaitable[ToolOutcome]],
    ) -> ToolDefinition[M]:
        """A tool whose code we own, described by one Pydantic model.

        Schema *and* validation come from `args_model`, so the two cannot
        disagree. Prefer this to the constructor for anything running in this
        process.
        """
        return ToolDefinition(
            name=name,
            description=description,
            input_schema=args_model.model_json_schema(),
            parse=args_model.model_validate,
            execute=execute,
        )

    def spec(self) -> ToolSpec:
        """The declaration handed to the model — **an allowlist**.

        Three fields, named explicitly. Adding a field to this dataclass cannot
        leak it into a request, which is the point: `execute` and `parse` are
        ours, and a model that could see them would be shown implementation it
        cannot use and might reason about.
        """
        return ToolSpec(
            name=self.name,
            description=self.description,
            input_schema=self.input_schema,
        )

    async def invoke(self, arguments: str, *, progress: ToolProgressReporter) -> ToolOutcome:
        """Parse the model's raw argument string, then run.

        Every failure mode returns a `Failure` rather than raising: malformed
        JSON, arguments the schema rejects, and a tool that blew up are all
        things the model can react to. Cancellation is the one exception — it is
        the caller's intent, not the tool's failure, so it propagates.
        """
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

        try:
            parsed = self.parse(raw)
        except ValidationError as err:
            return Failure(INVALID_ARGUMENTS, f"invalid arguments for {self.name!r}: {err}")

        try:
            return await self.execute(parsed, progress)
        except Exception as err:  # noqa: BLE001 — a tool's bug must not kill the turn
            return Failure(EXECUTION_ERROR, f"{self.name} failed: {type(err).__name__}: {err}")
