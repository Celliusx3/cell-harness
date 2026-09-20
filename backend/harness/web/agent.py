"""The agent the server composes: a model, the native tools, the guardrail."""

from __future__ import annotations

from harness.agent.compaction import CompactionService
from harness.agent.hooks import HookChain
from harness.agent.hooks.native.empty_reply import EmptyReplyHook
from harness.agent.hooks.native.exact_failure import ExactFailureHook
from harness.agent.hooks.native.no_progress import NoProgressHook
from harness.agent.hooks.native.repeated_call import RepeatedCallHook
from harness.agent.hooks.native.same_tool_failure import SameToolFailureHook
from harness.agent.loop import LoopAgent
from harness.config.settings import Settings
from harness.llm.adapters.openai import OpenAIClient
from harness.mcp.store import McpServerStore
from harness.sandbox import DenoRunner
from harness.session.service import SessionService
from harness.skills import SKILL, SkillService, skill_tool
from harness.tools.client import ClientTools, ClientToolService
from harness.tools.dispatcher import ToolDispatcher
from harness.tools.native.clock import clock_tool
from harness.tools.native.code import CODE_PROMPT, DETAILS, EXECUTE, LIST, code_mode_tools
from harness.tools.native.location import LOCATION_TOOL
from harness.tools.pipeline import ToolPipeline
from harness.tools.registry import ToolRegistry

SYSTEM_PROMPT = (
    "You are a helpful assistant. When a tool can answer the user's question, "
    "call it instead of guessing. You have a long-term memory in the memory "
    "functions: search it before answering about anything the user told you in "
    "an earlier conversation, and save what they ask you to remember."
)

CLIENT_TOOLS = ClientTools((LOCATION_TOOL,))
DEFAULT_TOOLS = (LIST, DETAILS, EXECUTE, SKILL, *sorted(CLIENT_TOOLS.names))


def build_agent(
    settings: Settings,
    store: SessionService,
    mcp: McpServerStore,
    skills: SkillService,
    client_tools: ClientToolService,
    context_tokens: int | None = None,
) -> LoopAgent:
    """The default agent: a model, the native tools, the guardrail, and a durability checkpoint."""
    registry = ToolRegistry([clock_tool(), *client_tools.definitions()])
    registry.add_provider(mcp.tools)
    registry.add_provider(lambda: [tool] if (tool := skill_tool(skills)) else [])

    dispatcher = ToolDispatcher(registry)
    for tool in code_mode_tools(
        registry=registry,
        dispatcher=dispatcher,
        runtime=DenoRunner(
            deno_path=settings.code.deno_path,
            timeout_seconds=settings.code.timeout_seconds,
        ),
        withheld=frozenset({SKILL, *CLIENT_TOOLS.names}),
    ):
        registry.register(tool)
    pipeline = ToolPipeline(registry, dispatcher, DEFAULT_TOOLS)

    client = OpenAIClient(settings.llm)
    system_prompt = SYSTEM_PROMPT + CODE_PROMPT

    return LoopAgent(
        name="default",
        model=settings.llm.model,
        client=client,
        tools=pipeline,
        system_prompt=system_prompt,
        checkpoint=store.flush,
        compaction=CompactionService(
            client=client,
            model=settings.llm.model,
            system_prompt=system_prompt,
            context_tokens=context_tokens,
        ),
        hooks=default_hooks(),
    )


def default_hooks() -> HookChain:
    """The four loop detectors, specific before general, and what to do about an empty reply."""
    return HookChain(
        (ExactFailureHook(), SameToolFailureHook(), NoProgressHook(), RepeatedCallHook()),
        steps=(EmptyReplyHook(),),
    )
