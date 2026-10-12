"""The runtime the server composes: a model, the native tools, the guardrail."""

from __future__ import annotations

import dataclasses
import logging

import httpx

from harness.bots import BotService
from harness.config.settings import Settings
from harness.llm.adapters.openai import OpenAIClient
from harness.mcp.service import McpService
from harness.prompts import CODE_PROMPT, GUIDANCE
from harness.runtime.hooks import HookChain
from harness.runtime.hooks.native.empty_reply import EmptyReplyHook
from harness.runtime.hooks.native.exact_failure import ExactFailureHook
from harness.runtime.hooks.native.no_progress import NoProgressHook
from harness.runtime.hooks.native.repeated_call import RepeatedCallHook
from harness.runtime.hooks.native.same_tool_failure import SameToolFailureHook
from harness.runtime.service import Runtime
from harness.runtime.subagents import Subagents
from harness.sandbox import DenoRunner
from harness.secrets import SecretService
from harness.session.service import SessionService
from harness.skills import SKILL, SkillService, skill_tool
from harness.tools.approval import ApprovalGate
from harness.tools.client import ClientTools, ClientToolService
from harness.tools.dispatcher import ToolDispatcher
from harness.tools.native.bots import BOT_CREATE, bot_create_tool
from harness.tools.native.clock import clock_tool
from harness.tools.native.code import DETAILS, EXECUTE, LIST, code_mode_tools
from harness.tools.native.location import LOCATION_TOOL
from harness.tools.native.question import QUESTION_TOOL
from harness.tools.native.secrets import (
    ASK_FOR_SECRET_TOOL,
    FETCH_WITH_SECRET,
    fetch_with_secret_tool,
)
from harness.tools.native.skills import (
    SKILL_DELETE,
    SKILL_SAVE,
    SKILL_WRITE_FILE,
    skill_delete_tool,
    skill_save_tool,
    skill_write_file_tool,
)
from harness.tools.native.subagent import RUN_SUBAGENT, run_subagent_tool
from harness.tools.pipeline import ToolPipeline
from harness.tools.registry import ToolRegistry

logger = logging.getLogger("harness.web")

CLIENT_TOOLS = ClientTools((LOCATION_TOOL, QUESTION_TOOL, ASK_FOR_SECRET_TOOL))
SKILL_WRITES = (SKILL_SAVE, SKILL_DELETE, SKILL_WRITE_FILE)
DEFAULT_TOOLS = (
    LIST,
    DETAILS,
    EXECUTE,
    SKILL,
    *SKILL_WRITES,
    BOT_CREATE,
    RUN_SUBAGENT,
    FETCH_WITH_SECRET,
    *sorted(CLIENT_TOOLS.names),
)
SUBAGENT_TOOLS = (LIST, DETAILS, EXECUTE, SKILL)
NOT_CALLABLE_FROM_SCRIPTS = frozenset(
    {SKILL, *SKILL_WRITES, BOT_CREATE, RUN_SUBAGENT, FETCH_WITH_SECRET, *CLIENT_TOOLS.names}
)


def build_runtime(
    settings: Settings,
    store: SessionService,
    mcp: McpService,
    skills: SkillService,
    client_tools: ClientToolService,
    gate: ApprovalGate,
    context_tokens: int | None = None,
    *,
    bots: BotService,
    subagent_logs: SessionService,
    secrets: SecretService,
) -> Runtime:
    """The default runtime: a model, the native tools, the guardrail, a durability checkpoint."""
    registry = ToolRegistry(
        [
            clock_tool(),
            skill_save_tool(skills),
            skill_delete_tool(skills),
            skill_write_file_tool(skills),
            bot_create_tool(bots),
            fetch_with_secret_tool(secrets, bots, httpx.AsyncHTTPTransport()),
            *client_tools.definitions(),
        ]
    )
    registry.add_provider(mcp.tools)
    registry.add_provider(lambda: [tool] if (tool := skill_tool(skills)) else [])

    logger.info("approval asks for: %s", sorted(gate.tools) or "nothing")
    dispatcher = ToolDispatcher(registry, gate)
    _register_code_mode(registry, dispatcher, settings)

    client = OpenAIClient(settings.llm)
    runtime = Runtime(
        model=settings.llm.model,
        client=client,
        tools=ToolPipeline(registry, dispatcher, DEFAULT_TOOLS),
        guidance=GUIDANCE,
        checkpoint=store.flush,
        context_tokens=context_tokens,
        hooks=default_hooks(),
    )
    _register_run_subagent(registry, dispatcher, runtime, subagent_logs)
    return runtime


def _register_code_mode(
    registry: ToolRegistry, dispatcher: ToolDispatcher, settings: Settings
) -> None:
    for tool in code_mode_tools(
        registry=registry,
        dispatcher=dispatcher,
        runner=DenoRunner(
            deno_path=settings.code.deno_path,
            timeout_seconds=settings.code.timeout_seconds,
        ),
        withheld=NOT_CALLABLE_FROM_SCRIPTS,
    ):
        registry.register(tool)


def _register_run_subagent(
    registry: ToolRegistry, dispatcher: ToolDispatcher, runtime: Runtime, logs: SessionService
) -> None:
    subagent = dataclasses.replace(
        runtime,
        tools=ToolPipeline(registry, dispatcher, SUBAGENT_TOOLS),
        guidance=CODE_PROMPT,
    )
    registry.register(run_subagent_tool(Subagents(subagent, logs)))


def default_hooks() -> HookChain:
    """The four loop detectors, specific before general, and what to do about an empty reply."""
    return HookChain(
        (ExactFailureHook(), SameToolFailureHook(), NoProgressHook(), RepeatedCallHook()),
        step_hooks=(EmptyReplyHook(),),
    )
