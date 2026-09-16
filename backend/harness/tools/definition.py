"""What a tool is, and what it returns.

Two ideas carry most of the weight here.

**The outcome is typed.** `Ok | Failure` rather than a string that starts with
`"error: "`. The model still sees the string — `render_outcome` produces it, and
a tolerant string is what lets the model recover instead of the turn dying — but
everything *inside* the harness switches on the type. The guardrail in phase 9
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

from pydantic import BaseModel, ConfigDict, ValidationError

from harness.llm.messages import Block, Text, ToolSpec, render_text
from harness.tools.context import ToolContext

# Joins a source to the tool it published — `yt` + `get_subtitles`. Here rather
# than in `mcp/` because it is the tool-name convention, and putting it there
# made every reader of a tool name import the MCP package.
NAMESPACE = "__"

# Failure codes. Stable identifiers the guardrail and UI switch on, distinct from
# the human-readable message beside them.
INVALID_ARGUMENTS = "INVALID_ARGUMENTS"
UNKNOWN_TOOL = "UNKNOWN_TOOL"
EXECUTION_ERROR = "EXECUTION_ERROR"
# A call that was not permitted to run. Distinct from an execution error because
# it is not a malfunction: nothing broke, the call was simply not allowed — the
# pipeline refusing a tool the model was never offered is the first case.
REFUSED = "REFUSED"
# Refused by a hook before it ran — the loop guardrail's answer to a call the
# model keeps repeating. Its own code so the guardrail can leave its own results
# out of what it counts.
BLOCKED = "BLOCKED"

# The prefix every tolerant failure wears on the wire. One constant, because the
# model learns this shape and a second spelling would read as a different kind of
# thing.
ERROR_PREFIX = "error: "


class ToolUi(BaseModel):
    """The interface a result is drawn with — MCP Apps' `_meta.ui.resourceUri`.

    Presentation, not prose: the model never sees it, the browser renders from it.
    `server` is which connection answers `resources/read` for `resource_uri` and
    the view's own `tools/call`; `data` is the result's `structuredContent`, kept
    beside the reference because that is what the view draws from, and a reloaded
    conversation must draw the same thing.
    """

    model_config = ConfigDict(frozen=True)

    server: str
    resource_uri: str
    data: object | None = None


@dataclass(frozen=True)
class Ok:
    """A call that produced a result.

    `content` is what the model reads: blocks, the Anthropic shape. Almost every
    tool returns one text block and passes a plain string, which `__post_init__`
    wraps. A tool that made others callable adds `ToolReference` blocks — that is
    the whole of how selection is stated, and it rides into the log with the
    result. `data` is the same result as a structured value, when the tool has
    one — an MCP server's `structuredContent`, say — because a *program* wants
    the object where the model wants prose. `ui` is tool-private presentation:
    set only by a tool bound to an MCP App, and read only by the browser.
    """

    content: tuple[Block, ...]
    data: object | None = None
    ui: ToolUi | None = None

    def __post_init__(self) -> None:
        if isinstance(self.content, str):
            object.__setattr__(self, "content", (Text(text=self.content),))

    @property
    def text(self) -> str:
        """The prose alone — for a reader that wants a string, like the bridge."""
        return render_text(self.content)


@dataclass(frozen=True)
class Failure:
    """A call that did not.

    Not an exception: an unknown tool, bad arguments, or a tool that raised are
    all ordinary traffic the model can recover from on the next step. Exceptions
    are reserved for our own bugs.
    """

    code: str
    message: str


@dataclass(frozen=True)
class Pending:
    """A call the *client* answers, later.

    Not a result and not a failure: the tool has nothing to compute, the
    person does. The loop ends the turn here with no result for the call; the
    answer arrives as the first event of a later turn. Vercel's "a tool with
    no `execute` is a client tool", spelled as an outcome so the dispatcher
    stays the one door and the loop never checks a tool's name.
    """


ToolOutcome = Ok | Failure | Pending


def render_outcome(outcome: Ok | Failure) -> tuple[Block, ...]:
    """What the model sees, as blocks.

    The only place a `Failure` is given its shape, so it cannot reach the model
    wearing two different ones: one text block, wearing the prefix. A
    `Pending` is never rendered — it has no result yet.
    """
    if isinstance(outcome, Ok):
        return outcome.content
    return (Text(text=f"{ERROR_PREFIX}{outcome.message}"),)


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

    def _missing_required(self, raw: dict) -> str | None:
        """A required field the model left out, told back as what it sent
        against what the schema has.

        Checked before `parse` and for every tool, because an MCP tool's parser
        is identity and the server's rejection is a pydantic dump that names the
        missing field but never the keys that arrived. The case that earned this:
        a model shown `declare function f(args: { id: string })` calls the tool
        directly with `{"args": {"id": "AAPL"}}` — three conversations, every
        direct markets call — and "id: Field required" told it nothing about the
        `args` it had wrapped the call in. Only missing *required* fields are
        the harness's business; an extra key is the tool's to accept or refuse.
        """
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

        if missing := self._missing_required(raw):
            return Failure(INVALID_ARGUMENTS, missing)

        try:
            parsed = self.parse(raw)
        except ValidationError as err:
            return Failure(INVALID_ARGUMENTS, f"invalid arguments for {self.name!r}: {err}")

        try:
            return await self.execute(parsed, context)
        except Exception as err:  # noqa: BLE001 — a tool's bug must not kill the turn
            return Failure(EXECUTION_ERROR, f"{self.name} failed: {type(err).__name__}: {err}")
