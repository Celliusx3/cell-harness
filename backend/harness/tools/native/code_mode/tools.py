"""The three tools that put a program between the model and its capabilities."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

from harness.llm import Text, ToolCall, ToolReference, text_of
from harness.prompts import NOTHING_CAME_BACK
from harness.sandbox import BridgeError, DenoUnavailableError, Runner, Script
from harness.tools.definition import ToolDefinition
from harness.tools.models.context import ToolContext
from harness.tools.models.outcome import (
    EXECUTION_ERROR,
    Failure,
    Ok,
    Pending,
    ToolOutcome,
)
from harness.tools.native.code_mode._typescript import declarations
from harness.tools.native.code_mode.models import DetailsArgs, ExecuteArgs, NoArgs
from harness.tools.native.code_mode.prompts import (
    EXECUTE_TYPESCRIPT,
    EXECUTE_TYPESCRIPT_DESCRIPTION,
    GET_FUNCTION_DETAILS,
    GET_FUNCTION_DETAILS_DESCRIPTION,
    IMAGES_STAY_OUT,
    LIST_FUNCTIONS,
    LIST_FUNCTIONS_DESCRIPTION,
)
from harness.tools.service import ToolService

AvailableTools = Callable[[], list[ToolDefinition]]

logger = logging.getLogger("harness.tools.code")


CODE_MODE_TOOL_NAMES = frozenset({LIST_FUNCTIONS, GET_FUNCTION_DETAILS, EXECUTE_TYPESCRIPT})


def code_mode_tools(
    *,
    tool_service: ToolService,
    runner: Runner,
    withheld: frozenset[str],
) -> list[ToolDefinition]:
    """The three tools, sharing one view of the catalog."""
    kept_out = CODE_MODE_TOOL_NAMES | withheld

    def available() -> list[ToolDefinition]:
        """Everything registered, minus ourselves and the withheld."""
        return [tool for tool in tool_service.all() if tool.name not in kept_out]

    return [
        _list_tool(available),
        _details_tool(available),
        _execute_tool(available, tool_service, runner, kept_out),
    ]


def _list_tool(available: AvailableTools) -> ToolDefinition[NoArgs]:
    async def execute(_args: NoArgs, _context: ToolContext) -> ToolOutcome:
        found = available()
        if not found:
            return Ok("No capabilities are available.")
        return Ok(declarations(found, with_types=False))

    return ToolDefinition.from_model(
        name=LIST_FUNCTIONS,
        description=LIST_FUNCTIONS_DESCRIPTION,
        args_model=NoArgs,
        execute=execute,
    )


def _details_tool(available: AvailableTools) -> ToolDefinition[DetailsArgs]:
    async def execute(args: DetailsArgs, _context: ToolContext) -> ToolOutcome:
        wanted = set(args.names)
        found = [tool for tool in available() if tool.name in wanted]
        missing = sorted(wanted - {tool.name for tool in found})
        if not found:
            return Ok(
                f"No functions named {', '.join(missing)}. Run {LIST_FUNCTIONS} to see what exists."
            )
        note = f"\n\n// not found: {', '.join(missing)}" if missing else ""
        return Ok(
            (
                Text(text=declarations(found, with_types=True) + note),
                *(ToolReference(tool_name=tool.name) for tool in found),
            )
        )

    return ToolDefinition.from_model(
        name=GET_FUNCTION_DETAILS,
        description=GET_FUNCTION_DETAILS_DESCRIPTION,
        args_model=DetailsArgs,
        execute=execute,
    )


def _execute_tool(
    available: AvailableTools, tool_service: ToolService, runner: Runner, kept_out: frozenset[str]
) -> ToolDefinition[ExecuteArgs]:
    async def execute(args: ExecuteArgs, context: ToolContext) -> ToolOutcome:
        names = [tool.name for tool in available()]
        try:
            script = await runner.run(
                args.code, names=names, bridge=_bridge(tool_service, context, kept_out)
            )
        except DenoUnavailableError as err:
            logger.error("the sandbox is unusable: %s", err)
            return Failure(EXECUTION_ERROR, f"the sandbox could not start: {err}")
        return _script_outcome(script)

    return ToolDefinition.from_model(
        name=EXECUTE_TYPESCRIPT,
        description=EXECUTE_TYPESCRIPT_DESCRIPTION,
        args_model=ExecuteArgs,
        execute=execute,
    )


def _bridge(tool_service: ToolService, context: ToolContext, kept_out: frozenset[str]):
    """One call from inside a script, dispatched as if the model made it."""
    counter = 0

    async def bridge(name: str, arguments: dict) -> object:
        nonlocal counter
        if name in kept_out:
            raise BridgeError(f"{name} cannot be called from inside a script")
        counter += 1
        call = ToolCall(id=f"sub:{counter}", name=name, arguments=json.dumps(arguments))
        outcome = await tool_service.dispatch(
            call,
            progress=context.progress,
            approved=False,
            origin=context.origin,
        )
        if isinstance(outcome, Ok) and outcome.images:
            raise BridgeError(IMAGES_STAY_OUT.format(name=name))
        if isinstance(outcome, Ok):
            return outcome.data if outcome.data is not None else _script_value(outcome.text)
        if isinstance(outcome, Pending):
            raise BridgeError(
                f"{name} waits for the user's approval, so a script cannot call it. "
                f"Read it with {GET_FUNCTION_DETAILS}, then call it directly as a tool."
            )
        raise BridgeError(text_of(outcome.content))

    return bridge


def _script_value(text: str) -> object:
    """A tool's text as the shape a script can actually use."""
    try:
        return json.loads(text)
    except ValueError:
        return text


def _script_outcome(script: Script) -> ToolOutcome:
    """What the model reads back."""
    printed = "\n".join(script.logs)
    if script.error is not None:
        detail = f"\n\nOutput before it failed:\n{printed}" if printed else ""
        return Failure(EXECUTION_ERROR, f"the script failed: {script.error}{detail}")

    returned = "" if script.result is None else f"Returned:\n{_json_text(script.result)}"
    body = "\n\n".join(part for part in (printed, returned) if part)
    return Ok(body or NOTHING_CAME_BACK, data=script.result)


def _json_text(value: object) -> str:
    try:
        return json.dumps(value, indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)
