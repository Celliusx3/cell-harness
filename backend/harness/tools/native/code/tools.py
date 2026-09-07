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

from harness.llm.messages import ToolCall
from harness.sandbox import BridgeError, DenoUnavailableError, Runner, Script
from harness.tools.definition import (
    EXECUTION_ERROR,
    Failure,
    Ok,
    ToolDefinition,
    ToolOutcome,
    render_outcome,
)
from harness.tools.dispatcher import ToolDispatcher
from harness.tools.native.code.typescript import declarations
from harness.tools.progress import ToolProgressReporter
from harness.tools.registry import ToolRegistry

# What the three tools read to build declarations. A callable rather than the
# registry so each factory says whether it needs the catalog at all.
Catalog = Callable[[], list[ToolDefinition]]

logger = logging.getLogger("harness.tools.code")

LIST = "list_functions"
DETAILS = "get_function_details"
EXECUTE = "execute_typescript"

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


LIST_DESCRIPTION = (
    "List every capability available, as TypeScript function signatures grouped "
    "by the server that provides them. Argument types are omitted — call "
    f"`{DETAILS}` for the ones you intend to use."
)

DETAILS_DESCRIPTION = (
    "Get full argument types for named functions. Ask for the few you need, not "
    "everything: the point of the two steps is that you never load the rest."
)

# Prompt text is code. "ONE script" exists because a model given a code tool
# otherwise calls it once per tool; the return/log rule exists because keeping
# intermediate values out of the conversation is the other half of the saving.
EXECUTE_DESCRIPTION = (
    "Run one TypeScript program that calls the capabilities you loaded.\n"
    "- Write ONE script that does the whole task. Several tool calls in one "
    "script cost one round-trip; several scripts cost one each.\n"
    "- Every call is async: `const r = await yt__get_subtitles({url});`.\n"
    "- A call returns an object when the tool publishes structured data, and "
    "text otherwise. Log it before assuming its shape.\n"
    "- A failed call throws — `try`/`catch` it and carry on.\n"
    "- Only what you `return` or `console.log` comes back. Everything else stays "
    "in the sandbox, so fetch freely and extract just what you need.\n"
    "- There is no network and no filesystem. The functions are the only way out."
)

# Separate from the tool descriptions: a model decides what it is capable of
# before it reads any of them.
CODE_PROMPT = (
    "\n\nYour capabilities are not in your tool list. They are TypeScript "
    f"functions you discover with `{LIST}`, type with `{DETAILS}`, and call from "
    f"a program you pass to `{EXECUTE}`. Prefer one program that does the whole "
    "task over several that each do a step. Never tell the user you lack a "
    "capability without listing the functions first."
)


def code_mode_tools(
    *, registry: ToolRegistry, dispatcher: ToolDispatcher, runtime: Runner
) -> list[ToolDefinition]:
    """The three tools, sharing one view of the catalog."""

    def available() -> list[ToolDefinition]:
        """Everything registered, minus ourselves. Read afresh, so a server that
        connects mid-conversation is findable on the next call."""
        return [tool for tool in registry.all() if tool.name not in RESERVED]

    return [
        _list_tool(available),
        _details_tool(available),
        _execute_tool(available, dispatcher, runtime),
    ]


def _list_tool(available: Catalog) -> ToolDefinition[BaseModel]:
    class NoArgs(BaseModel):
        pass

    async def execute(_args: NoArgs, _progress: ToolProgressReporter) -> ToolOutcome:
        found = available()
        if not found:
            return Ok("No capabilities are available.")
        return Ok(declarations(found, types=False))

    return ToolDefinition.from_model(
        name=LIST, description=LIST_DESCRIPTION, args_model=NoArgs, execute=execute
    )


def _details_tool(available: Catalog) -> ToolDefinition[DetailsArgs]:
    async def execute(args: DetailsArgs, _progress: ToolProgressReporter) -> ToolOutcome:
        wanted = set(args.names)
        found = [tool for tool in available() if tool.name in wanted]
        missing = sorted(wanted - {tool.name for tool in found})
        if not found:
            # `Ok`, not `Failure` — the names were wrong, nothing broke.
            return Ok(f"No functions named {', '.join(missing)}. Run {LIST} to see what exists.")
        note = f"\n\n// not found: {', '.join(missing)}" if missing else ""
        return Ok(declarations(found, types=True) + note)

    return ToolDefinition.from_model(
        name=DETAILS, description=DETAILS_DESCRIPTION, args_model=DetailsArgs, execute=execute
    )


def _execute_tool(
    available: Catalog, dispatcher: ToolDispatcher, runtime: Runner
) -> ToolDefinition[ExecuteArgs]:
    async def execute(args: ExecuteArgs, progress: ToolProgressReporter) -> ToolOutcome:
        names = [tool.name for tool in available()]
        try:
            script = await runtime.run(args.code, names=names, bridge=_bridge(dispatcher, progress))
        except DenoUnavailableError as err:
            # Not recoverable by rewriting the script, so it does not invite one.
            logger.error("the sandbox is unusable: %s", err)
            return Failure(EXECUTION_ERROR, f"the sandbox could not start: {err}")
        return _rendered(script)

    return ToolDefinition.from_model(
        name=EXECUTE, description=EXECUTE_DESCRIPTION, args_model=ExecuteArgs, execute=execute
    )


def _bridge(dispatcher: ToolDispatcher, progress: ToolProgressReporter):
    """One call from inside a script, dispatched as if the model made it.

    The sandbox deals in plain values and `BridgeError`; the harness deals in
    `Ok`/`Failure`. This is the only place the two vocabularies meet.
    """
    counter = 0

    async def bridge(name: str, arguments: dict) -> object:
        nonlocal counter
        if name in RESERVED:
            raise BridgeError(f"{name} cannot be called from inside a script")
        counter += 1
        # A shape no provider issues, so a later phase can key nested tool cards
        # on it unambiguously.
        call = ToolCall(id=f"sub:{counter}", name=name, arguments=json.dumps(arguments))
        outcome = await dispatcher.dispatch(call, progress=progress)
        if isinstance(outcome, Ok):
            return outcome.data if outcome.data is not None else _as_value(outcome.content)
        raise BridgeError(render_outcome(outcome))

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
    return Ok(
        body or "The script finished without returning or printing anything.", data=script.result
    )


def _json(value: object) -> str:
    try:
        return json.dumps(value, indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)
