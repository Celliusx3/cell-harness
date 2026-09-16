"""The agent the server composes: a model, the native tools, the guardrail.

Split from `server.py` at the length cap, along the seam that was already
there — everything below is about what the model is offered and how a call
runs; nothing about HTTP or channels.
"""

from __future__ import annotations

from harness.agent.hooks import HookChain
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
    "call it instead of guessing."
)

# What the model is offered on every request, whatever else is registered.
# Everything not named here is still callable — the model reaches it by writing a
# program — it is simply not described in the request, which is what stops that
# description being re-uploaded with every message.
#
# **This is the list to edit.** To stop the model writing a program just to read
# the clock, import `CLOCK` from `tools.native.clock` and add it. The cost is
# that tool's schema in every request, forever.
#
# Prefer a constant over a literal. A name spelled here and defined elsewhere is
# a rename that half-happens, and `specs()` skips a name it cannot find without
# complaining. MCP tools have no constant to import — `"jobs__search"` is a
# literal by necessity, and unchecked until that server connects.
#
# `skill` is here because a skill's body is context for the model, not data for
# a program — see `withheld` in `build_agent`. Present only while a skill exists:
# the provider yields nothing otherwise, and `specs()` skips an absent name.
#
# Every client tool is here so asking costs no discovery round trip: a
# no-arg schema each, and a model not shown `get_location` answers "I don't
# know where you are" instead of asking.
#
# **A new client tool is one entry in `CLIENT_TOOLS`** and one handler in the
# browser's map; it is offered, and kept from scripts, by being there.
CLIENT_TOOLS = ClientTools((LOCATION_TOOL,))
DEFAULT_TOOLS = (LIST, DETAILS, EXECUTE, SKILL, *sorted(CLIENT_TOOLS.names))


def build_agent(
    settings: Settings,
    store: SessionService,
    mcp: McpServerStore,
    skills: SkillService,
    client_tools: ClientToolService,
) -> LoopAgent:
    """The default agent: a model, the native tools, the guardrail, and a
    durability checkpoint.

    This is what stands in for dsh's config-driven plugin tree. A missing
    dependency is a `TypeError` here rather than a runtime surprise, which is the
    whole reason we do not need an injection framework.
    """
    registry = ToolRegistry([clock_tool(), *client_tools.definitions()])
    # Registered once and never again — the disposer is deliberately dropped.
    # Connecting and disconnecting change what this *yields*, not whether it is
    # here, which is what makes a server added mid-conversation callable on the
    # next turn without rebuilding the agent.
    registry.add_provider(mcp.tools)
    # Same shape as MCP's: the tool is rebuilt from the catalog every time the
    # registry is read, so a skill added to a root is in the next request's enum,
    # and the last one deleted takes the tool with it.
    registry.add_provider(lambda: [tool] if (tool := skill_tool(skills)) else [])

    # One dispatcher, shared. Two would let a future approval gate be installed
    # on the model's path and not on a script's, with nothing to say which.
    dispatcher = ToolDispatcher(registry)
    # The disposer is dropped for the same reason MCP's is: these live as long as
    # the process.
    for tool in code_mode_tools(
        registry=registry,
        dispatcher=dispatcher,
        runtime=DenoRunner(
            deno_path=settings.code.deno_path,
            timeout_seconds=settings.code.timeout_seconds,
        ),
        # A script may not load a skill: the body is for the model to read, and
        # `list_functions` must not advertise it as a capability. Nor may it
        # ask the client for anything: a script's timeout is shorter than a
        # person's, and the model is the one to decide when to ask.
        withheld=frozenset({SKILL, *CLIENT_TOOLS.names}),
    ):
        registry.register(tool)
    # Last, because nothing else needs it — three schemas however many servers
    # are connected. See `DEFAULT_TOOLS`.
    pipeline = ToolPipeline(registry, dispatcher, DEFAULT_TOOLS)

    return LoopAgent(
        name="default",
        model=settings.llm.model,
        client=OpenAIClient(settings.llm),
        tools=pipeline,
        # The prompt travels with the tools: a model shown three unfamiliar tools
        # and not told what they are for will answer "I can't do that" rather
        # than discover its own capabilities.
        system_prompt=SYSTEM_PROMPT + CODE_PROMPT,
        # Durability where it matters: before every model request, and before
        # every tool that might have a side effect.
        checkpoint=store.flush,
        # The one place the loop guardrail is installed. Delete it and the loop
        # runs unhooked — nothing in `agent/` knows it was here. The detectors
        # are asked in this order, and the first with something to say wins:
        # specific before general.
        hooks=HookChain(
            (
                ExactFailureHook(),
                SameToolFailureHook(),
                NoProgressHook(),
                RepeatedCallHook(),
            )
        ),
    )
