"""The three tools that put a program between the model and its capabilities."""

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

Catalog = Callable[[], list[ToolDefinition]]

logger = logging.getLogger("harness.tools.code")


RESERVED = frozenset({LIST, DETAILS, EXECUTE})
NOTHING_CAME_BACK = (
    "The script ran but returned nothing and printed nothing, so nothing came "
    "back to you — no data has been fetched."
)


class DetailsArgs(BaseModel):
    """Arguments for `get_function_details`."""

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
    withheld: frozenset[str],
) -> list[ToolDefinition]:
    """The three tools, sharing one view of the catalog."""
    kept_out = RESERVED | withheld

    def available() -> list[ToolDefinition]:
        """Everything registered, minus ourselves and the withheld."""
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
            return Ok(f"No functions named {', '.join(missing)}. Run {LIST} to see what exists.")
        note = f"\n\n// not found: {', '.join(missing)}" if missing else ""
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
            logger.error("the sandbox is unusable: %s", err)
            return Failure(EXECUTION_ERROR, f"the sandbox could not start: {err}")
        return _rendered(script)

    return ToolDefinition.from_model(
        name=EXECUTE, description=EXECUTE_DESCRIPTION, args_model=ExecuteArgs, execute=execute
    )


def _bridge(dispatcher: ToolDispatcher, progress: ToolProgressReporter, kept_out: frozenset[str]):
    """One call from inside a script, dispatched as if the model made it."""
    counter = 0

    async def bridge(name: str, arguments: dict) -> object:
        nonlocal counter
        if name in kept_out:
            raise BridgeError(f"{name} cannot be called from inside a script")
        counter += 1
        call = ToolCall(id=f"sub:{counter}", name=name, arguments=json.dumps(arguments))
        outcome = await dispatcher.dispatch(call, progress=progress, approved=False)
        if isinstance(outcome, Ok):
            return outcome.data if outcome.data is not None else _as_value(outcome.text)
        if isinstance(outcome, Pending):
            raise BridgeError(
                f"{name} waits for the user's approval, so a script cannot call it. "
                f"Read it with {DETAILS}, then call it directly as a tool."
            )
        raise BridgeError(render_text(render_outcome(outcome)))

    return bridge


def _as_value(content: str) -> object:
    """A tool's text as the shape a script can actually use."""
    try:
        return json.loads(content)
    except ValueError:
        return content


def _rendered(script: Script) -> ToolOutcome:
    """What the model reads back."""
    printed = "\n".join(script.logs)
    if script.error is not None:
        detail = f"\n\nOutput before it failed:\n{printed}" if printed else ""
        return Failure(EXECUTION_ERROR, f"the script failed: {script.error}{detail}")

    returned = "" if script.result is None else f"Returned:\n{_json(script.result)}"
    body = "\n\n".join(part for part in (printed, returned) if part)
    return Ok(body or NOTHING_CAME_BACK, data=script.result)


def _json(value: object) -> str:
    try:
        return json.dumps(value, indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)
