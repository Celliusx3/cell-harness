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

from harness.agent.loop import LoopAgent
from harness.config.settings import Settings, load
from harness.llm.adapters.openai import OpenAIClient
from harness.runs.store import RunStore
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.tools.native.clock import clock_tool
from harness.tools.pipeline import ToolPipeline
from harness.tools.registry import ToolRegistry
from harness.web.routes import conversations

SYSTEM_PROMPT = (
    "You are a helpful assistant. When a tool can answer the user's question, "
    "call it instead of guessing."
)


def build_store(settings: Settings) -> SessionService:
    """The session service over the configured storage backend.

    Swapping JSONL for SQLite is this line and nothing else — `SessionService`
    depends on the `SessionRepository` Protocol, never on a concrete backend.
    """
    return SessionService(JsonlSessionRepository(settings.sessions.root))


def build_agent(settings: Settings, store: SessionService) -> LoopAgent:
    """The default agent: a model, the native tools, and a durability checkpoint.

    This is what stands in for dsh's config-driven plugin tree. A missing
    dependency is a `TypeError` here rather than a runtime surprise, which is the
    whole reason we do not need an injection framework.
    """
    registry = ToolRegistry([clock_tool()])
    return LoopAgent(
        name="default",
        model=settings.llm.model,
        client=OpenAIClient(settings.llm),
        tools=ToolPipeline(registry),
        system_prompt=SYSTEM_PROMPT,
        # Durability where it matters: before every model request, and before
        # every tool that might have a side effect.
        checkpoint=store.flush,
    )


def create_web_app() -> FastAPI:
    """The application uvicorn starts.

    Zero arguments, because `--factory` calls it with none. Settings are loaded
    here rather than at import, so a missing API key is a `MissingConfigError`
    naming the file to edit instead of an import-time traceback.
    """
    settings = load()
    service = build_store(settings)
    return create_app(service, RunStore(service, build_agent(settings, service)))


def create_app(service: SessionService, runs: RunStore) -> FastAPI:
    """The HTTP surface over one service and one run store."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        # Turns still in flight when the server stops are cancelled *and
        # flushed*, so an interrupted conversation stays resumable. Exiting
        # underneath them would leave exactly the unanswered tool calls phase 3's
        # repair exists to clean up — recoverable, but there is no reason to
        # create the damage on an orderly shutdown.
        await runs.aclose()

    app = FastAPI(title="cell-harness", lifespan=lifespan)
    app.state.service = service
    app.state.runs = runs
    app.include_router(conversations.router)
    return app
