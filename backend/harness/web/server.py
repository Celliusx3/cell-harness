"""The composition root, and the ASGI application.

Two entry points. `create_web_app()` takes no arguments and builds the whole
object graph — that is what `uvicorn --factory` needs, and what `make dev` points
at. `create_app(service, runs)` takes its dependencies, which is what the tests
drive so they exercise the real application with a fake model client rather than a
near-copy of it.

The object graph is assembled here rather than in a module of its own. It was
briefly separate, back when a terminal CLI needed it too; with the browser as the
only surface there is one caller, and a `compose.py` with one consumer is a file
to open on the way to the answer. cell-bot puts its composition in
`web/server.py` for the same reason.

**Host and port are not here, and not in `config.json` either.** They belong to
the launch, so they live in the `Makefile` beside the uvicorn invocation, the way
cell-bot does it. Two reasons that beats a setting:

- The port has a second reader that cannot see Python at all — the frontend's dev
  proxy in `frontend/next.config.ts`. A setting would look authoritative while the
  frontend silently kept proxying to the old port, and the symptom is a rewrite
  failing with ECONNREFUSED rather than anything naming the cause.
- Uvicorn already defaults the host to `127.0.0.1`, which is what we want: the
  harness holds a provider key and runs a model loop with nothing authenticating
  in front of it, so `0.0.0.0` would hand the local network an unauthenticated
  agent. Passing it explicitly would only restate the default.

State lives on `app.state`, read through the accessors in
`routes/conversations.py`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from harness.agent.hooks import HookChain
from harness.agent.hooks.native.exact_failure import ExactFailureHook
from harness.agent.hooks.native.no_progress import NoProgressHook
from harness.agent.hooks.native.repeated_call import RepeatedCallHook
from harness.agent.hooks.native.same_tool_failure import SameToolFailureHook
from harness.agent.loop import LoopAgent
from harness.channels.discord.channel import DiscordChannel
from harness.channels.gateway import ChannelGateway
from harness.channels.repositories.jsonl import JsonlChatRepository
from harness.channels.telegram.channel import TelegramChannel
from harness.channels.web.channel import WebChannel
from harness.config.settings import Settings, load
from harness.llm.adapters.openai import OpenAIClient
from harness.mcp.store import McpServerStore
from harness.runs.store import RunStore
from harness.sandbox import DenoRunner
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.skills import SKILL, Catalog, SkillCatalog, skill_tool
from harness.tools.dispatcher import ToolDispatcher
from harness.tools.native.clock import clock_tool
from harness.tools.native.code import CODE_PROMPT, DETAILS, EXECUTE, LIST, code_mode_tools
from harness.tools.pipeline import ToolPipeline
from harness.tools.registry import ToolRegistry
from harness.web.logs import configure_logging
from harness.web.routes.mcp import build_router as build_mcp_router
from harness.web.routes.skills import build_router as build_skills_router

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
DEFAULT_TOOLS = (LIST, DETAILS, EXECUTE, SKILL)


def build_store(settings: Settings) -> SessionService:
    """The session service over the configured storage backend.

    Swapping JSONL for SQLite is this line and nothing else — `SessionService`
    depends on the `SessionRepository` Protocol, never on a concrete backend.
    """
    return SessionService(JsonlSessionRepository(settings.sessions.root))


def build_mcp(settings: Settings) -> McpServerStore:
    """Connections to whatever `config.json` declares under `mcp.servers`."""
    return McpServerStore(settings.mcp.servers)


def build_agent(
    settings: Settings, store: SessionService, mcp: McpServerStore, skills: Catalog
) -> LoopAgent:
    """The default agent: a model, the native tools, the guardrail, and a
    durability checkpoint.

    This is what stands in for dsh's config-driven plugin tree. A missing
    dependency is a `TypeError` here rather than a runtime surprise, which is the
    whole reason we do not need an injection framework.
    """
    registry = ToolRegistry([clock_tool()])
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
        # `list_functions` must not advertise it as a capability.
        withheld=frozenset({SKILL}),
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


def build_channels(
    settings: Settings, sessions: SessionService, runs: RunStore
) -> tuple[ChannelGateway, WebChannel]:
    """The gateway, and a runtime per configured platform.

    **Where a new platform is added**, and the only place: a block like
    Telegram's below, and nothing else in the codebase moves. Everything between
    "a message arrived" and "a reply is ready" is already shared.

    Wiring is deliberately linear — build the gateway, build the channel with
    it, register the channel back. An earlier version had the platform build the
    gateway through a factory callback, which was a circular dependency wearing a
    disguise.

    @returns the gateway, which also supervises every channel it was given, so
    the server has one thing to start and one thing to stop — and the web channel
    beside it, because `create_app` needs the router that channel owns and the
    gateway deliberately knows nothing about HTTP.
    """
    # Chat state lives beside the sessions it points at, so one directory is the
    # whole of this harness's durable state, and every platform shares it — the
    # channel name is part of a chat's identity, so they cannot collide.
    chats = JsonlChatRepository(settings.sessions.root.parent / "chats")
    gateway = ChannelGateway(chats, runs, sessions, public_url=settings.web.public_url)

    # Unconditional, because the browser is the product's floor — there is no
    # configuration in which the HTTP API is absent. It registers like any other
    # platform, which is the point of this phase: the browser is a client of a
    # channel, the way the Telegram app is a client of Telegram.
    web = WebChannel(sessions, runs, gateway)
    gateway.register(web)

    # Absent by default rather than failing: a token cannot be guessed, and the
    # browser is a complete product without one. The guard is load-bearing —
    # building the channel anyway hands PTB an empty token. `.strip()` because a
    # blank string in JSON is a paste that went wrong, not a deliberate value.
    if settings.telegram.bot_token.strip():
        gateway.register(TelegramChannel(settings.telegram.bot_token, gateway))

    # Same guard, same reason.
    if settings.discord.bot_token.strip():
        gateway.register(DiscordChannel(settings.discord.bot_token, gateway))

    return gateway, web


def create_web_app() -> FastAPI:
    """The application uvicorn starts.

    Zero arguments, because `--factory` calls it with none. Settings are loaded
    here rather than at import, so a missing API key is a `MissingConfigError`
    naming the file to edit instead of an import-time traceback.
    """
    configure_logging()
    settings = load()
    service = build_store(settings)
    mcp = build_mcp(settings)
    # One catalog for the agent and the settings API, so what the page lists and
    # what the model is offered are the same read.
    skills = SkillCatalog(settings.skills.roots)
    runs = RunStore(service, build_agent(settings, service, mcp, skills))
    gateway, web = build_channels(settings, service, runs)
    return create_app(runs, gateway, web, mcp, skills)


def create_app(
    runs: RunStore,
    gateway: ChannelGateway,
    web: WebChannel,
    mcp: McpServerStore,
    skills: Catalog,
) -> FastAPI:
    """The HTTP surface, mounted from the channel that owns it.

    The gateway is no longer optional. It was, while the browser bypassed it and a
    bot token was the only reason to have one; now the browser *is* a channel, so
    an app without a gateway would have no routes at all.

    Nothing is put on `app.state`. The routes close over their channel instead,
    so what a handler needs is given to it rather than fetched from wherever the
    app happened to stash it.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Before the gateway: a message arriving the instant a channel starts
        # would otherwise be answered by an agent whose MCP tools are still absent.
        await mcp.start()
        await gateway.start()
        yield
        # Before `runs.aclose()`: the gateway stops listening and then stops
        # delivering, so nothing is still trying to send a message for a turn
        # being cancelled underneath it. The ordering *within* that is the
        # gateway's own — see its `aclose`.
        await gateway.aclose()
        # Turns still in flight when the server stops are cancelled *and
        # flushed*, so an interrupted conversation stays resumable. Exiting
        # underneath them would leave exactly the unanswered tool calls phase 3's
        # repair exists to clean up — recoverable, but there is no reason to
        # create the damage on an orderly shutdown.
        await runs.aclose()
        # After `runs.aclose()`: a turn still settling may be inside a tool call,
        # and closing its server first would answer that call with a disconnect.
        await mcp.aclose()

    app = FastAPI(title="cell-harness", lifespan=lifespan)
    app.include_router(web.router)
    app.include_router(build_skills_router(skills))
    app.include_router(build_mcp_router(mcp))
    return app
