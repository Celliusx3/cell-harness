"""The three tools that put a program between the model and its capabilities.

    list_functions()          what exists, signatures only
    get_function_details(…)   full types for the few that matter
    execute_typescript(…)     one script that calls them

Every call inside a script goes back through `ToolPipeline`, so a script reaches
exactly what the model could have, by the same route. See
`docs/mcp-tool-scaling.md` §6.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

from pydantic import BaseModel, Field

from harness.llm.messages import Text, ToolCall, ToolReference, render_text
from harness.sandbox import BridgeError, DenoUnavailableError, Runner, Script
from harness.tools.context import ToolContext
from harness.tools.definition import (
    EXECUTION_ERROR,
    Failure,
    Ok,
    Pending,
    ToolDefinition,
    ToolOutcome,
    render_outcome,
)
from harness.tools.dispatcher import ToolDispatcher
from harness.tools.native.code.prompts import (
    DETAILS,
    DETAILS_DESCRIPTION,
    EXECUTE,
    EXECUTE_DESCRIPTION,
    LIST,
    LIST_DESCRIPTION,
)
from harness.tools.native.code.typescript import declarations
from harness.tools.progress import ToolProgressReporter
from harness.tools.registry import ToolRegistry

# What the three tools read to build declarations. A callable rather than the
# registry so each factory says whether it needs the catalog at all.
Catalog = Callable[[], list[ToolDefinition]]

logger = logging.getLogger("harness.tools.code")


# Dispatchable like any other tool, which is what keeps the loop and the log
# unaware of code mode — but withheld from scripts: Deno inside Deno is unbounded.
# Whether the model is *offered* them is not decided here: see `DEFAULT_TOOLS` in
# the composition root.
RESERVED = frozenset({LIST, DETAILS, EXECUTE})


class DetailsArgs(BaseModel):
    """Descriptions here are read by the model, not by us."""

    names: list[str] = Field(
        description="Exact function names from list_functions, e.g. ['yt__get_subtitles']."
    )


class ExecuteArgs(BaseModel):
    code: str = Field(
        description=(
            "The body of an async function. Call tools by their exact name — "
            "`await yt__get_subtitles({url})`. Use `return` for the answer and "
            "`console.log` for anything else worth seeing."
        )
    )
    description: str = Field(description="One line saying what the program does.")


def code_mode_tools(
    *,
    registry: ToolRegistry,
    dispatcher: ToolDispatcher,
    runtime: Runner,
    withheld: frozenset[str] = frozenset(),
) -> list[ToolDefinition]:
    """The three tools, sharing one view of the catalog.

    `withheld` names tools a script may not reach on top of our own three: ones
    whose result is context for the model rather than data for a program — the
    `skill` tool's body, today. A script fetching it would only `return` it into
    the conversation by a slower route, and `list_functions` advertising it as a
    capability invites exactly that. The composition root decides which, so
    this module knows nothing about skills.
    """
    kept_out = RESERVED | withheld

    def available() -> list[ToolDefinition]:
        """Everything registered, minus ourselves and the withheld. Read afresh,
        so a server that connects mid-conversation is findable on the next call.

        **The one chokepoint for what the model can see.** All three tools read
        it, so a withheld tool is absent from the signatures, from the full
        types, and from the names the sandbox binds as globals — the third being
        the one that makes it uncallable rather than merely undocumented.
        """
        return [tool for tool in registry.all() if tool.name not in kept_out]

    return [
        _list_tool(available),
        _details_tool(available),
        _execute_tool(available, dispatcher, runtime, kept_out),
    ]


def _list_tool(available: Catalog) -> ToolDefinition[BaseModel]:
    class NoArgs(BaseModel):
        pass

    async def execute(_args: NoArgs, _context: ToolContext) -> ToolOutcome:
        found = available()
        if not found:
            return Ok("No capabilities are available.")
        return Ok(declarations(found, types=False))

    return ToolDefinition.from_model(
        name=LIST, description=LIST_DESCRIPTION, args_model=NoArgs, execute=execute
    )


def _details_tool(available: Catalog) -> ToolDefinition[DetailsArgs]:
    async def execute(args: DetailsArgs, _context: ToolContext) -> ToolOutcome:
        wanted = set(args.names)
        found = [tool for tool in available() if tool.name in wanted]
        missing = sorted(wanted - {tool.name for tool in found})
        if not found:
            # `Ok`, not `Failure` — the names were wrong, nothing broke.
            return Ok(f"No functions named {', '.join(missing)}. Run {LIST} to see what exists.")
        note = f"\n\n// not found: {', '.join(missing)}" if missing else ""
        # The references are the fact, stated where it happens: the model has
        # read these. What that means for its tool list is the pipeline's, and
        # how it is told is the adapter's. An absent name is not in `found`, so
        # it is never referenced.
        return Ok(
            (
                Text(text=declarations(found, types=True) + note),
                *(ToolReference(tool_name=tool.name) for tool in found),
            )
        )

    return ToolDefinition.from_model(
        name=DETAILS, description=DETAILS_DESCRIPTION, args_model=DetailsArgs, execute=execute
    )


def _execute_tool(
    available: Catalog, dispatcher: ToolDispatcher, runtime: Runner, kept_out: frozenset[str]
) -> ToolDefinition[ExecuteArgs]:
    async def execute(args: ExecuteArgs, context: ToolContext) -> ToolOutcome:
        names = [tool.name for tool in available()]
        try:
            script = await runtime.run(
                args.code, names=names, bridge=_bridge(dispatcher, context.progress, kept_out)
            )
        except DenoUnavailableError as err:
            # Not recoverable by rewriting the script, so it does not invite one.
            logger.error("the sandbox is unusable: %s", err)
            return Failure(EXECUTION_ERROR, f"the sandbox could not start: {err}")
        return _rendered(script)

    return ToolDefinition.from_model(
        name=EXECUTE, description=EXECUTE_DESCRIPTION, args_model=ExecuteArgs, execute=execute
    )


def _bridge(dispatcher: ToolDispatcher, progress: ToolProgressReporter, kept_out: frozenset[str]):
    """One call from inside a script, dispatched as if the model made it.

    The sandbox deals in plain values and `BridgeError`; the harness deals in
    `Ok`/`Failure`. This is the only place the two vocabularies meet.
    """
    counter = 0

    async def bridge(name: str, arguments: dict) -> object:
        nonlocal counter
        if name in kept_out:
            raise BridgeError(f"{name} cannot be called from inside a script")
        counter += 1
        # A shape no provider issues, so a later phase can key nested tool cards
        # on it unambiguously.
        call = ToolCall(id=f"sub:{counter}", name=name, arguments=json.dumps(arguments))
        outcome = await dispatcher.dispatch(call, progress=progress)
        if isinstance(outcome, Ok):
            return outcome.data if outcome.data is not None else _as_value(outcome.text)
        if isinstance(outcome, Pending):  # unreachable: client tools are kept out
            raise BridgeError(f"{name} is answered by the user, not a script")
        raise BridgeError(render_text(render_outcome(outcome)))

    return bridge


def _as_value(content: str) -> object:
    """A tool's text as the shape a script can actually use.

    Most MCP servers publish JSON as *text* rather than `structuredContent`, so
    without this a script indexing the result gets a string and silently reads
    `undefined`. Observed live: a model wrote `results.jobs`, got nothing, and
    burned five scripts failing to work out why.

    Text that is not JSON is returned untouched, so a tool returning prose still
    reads as prose.
    """
    try:
        return json.loads(content)
    except ValueError:
        return content


def _rendered(script: Script) -> ToolOutcome:
    """What the model reads back. Logs survive a failure on purpose — a script
    that threw halfway is debugged from what it printed before it did."""
    printed = "\n".join(script.logs)
    if script.error is not None:
        detail = f"\n\nOutput before it failed:\n{printed}" if printed else ""
        return Failure(EXECUTION_ERROR, f"the script failed: {script.error}{detail}")

    returned = "" if script.result is None else f"Returned:\n{_json(script.result)}"
    body = "\n\n".join(part for part in (printed, returned) if part)
    # The consequence, not the observation. "Finished without printing anything"
    # was read as success four times in a row by a 4B model that had declared
    # `main` and never called it; the report that followed had invented figures.
    return Ok(
        body
        or "The script ran but returned nothing and printed nothing, so nothing came "
        "back to you — no data has been fetched.",
        data=script.result,
    )


def _json(value: object) -> str:
    try:
        return json.dumps(value, indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)
