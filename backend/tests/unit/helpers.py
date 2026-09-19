"""Assertions and builders shared across test modules."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable, Sequence
from contextlib import aclosing
from datetime import UTC, datetime
from pathlib import Path

from harness.agent.compaction import CompactionService
from harness.agent.hooks import HookChain
from harness.agent.loop import LoopAgent
from harness.config.settings import SkillSettings
from harness.llm.messages import AssistantMessage, Message, ToolMessage
from harness.runs.store import RunStore
from harness.session.log import Session
from harness.session.models import SessionHeader
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.skills import SkillService
from harness.tools.client import ClientToolService
from harness.tools.context import ToolContext
from harness.tools.definition import ToolDefinition
from harness.tools.dispatcher import ToolDispatcher
from harness.tools.pipeline import ToolPipeline
from harness.tools.registry import ToolProvider, ToolRegistry
from harness.web.agent import CLIENT_TOOLS


def unanswered_calls(messages: Sequence[Message]) -> list[str]:
    """Tool call ids with no matching tool message."""
    answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    return [
        call.id
        for m in messages
        if isinstance(m, AssistantMessage)
        for call in m.tool_calls
        if call.id not in answered
    ]


async def no_progress(*, percent: float | None, message: str | None) -> None:
    """A reporter that discards, for tests with nowhere to put progress."""
    return None


def context_for(call_id: str = "call-1") -> ToolContext:
    """A context for invoking a tool directly, outside the dispatcher."""
    return ToolContext(call_id=call_id, progress=no_progress)


def new_session(session_id: str = "s") -> Session:
    """A session with a throwaway header, for tests that only care about the log."""
    return Session(SessionHeader(id=session_id, created_at=datetime(2026, 1, 1, tzinfo=UTC)))


def pipeline_for(
    *tools: ToolDefinition,
    providers: Sequence[ToolProvider] = (),
    offer: Sequence[str] = (),
) -> ToolPipeline:
    """A registry, a dispatcher and a pipeline over `tools`, offering all of them."""
    registry = ToolRegistry(tools, providers=providers)
    names = [*(tool.name for tool in tools), *offer]
    return ToolPipeline(registry, ToolDispatcher(registry), default_tools=names)


def loop_agent(
    client,
    *tools: ToolDefinition,
    system_prompt: str = "",
    hooks: HookChain | None = None,
    checkpoint: Callable[[Session], Awaitable[None]] | None = None,
    compaction: CompactionService | None = None,
) -> LoopAgent:
    """An agent over `tools`, with no pipeline at all when there are none."""
    return LoopAgent(
        name="t",
        model="m",
        client=client,
        tools=pipeline_for(*tools) if tools else None,
        system_prompt=system_prompt,
        hooks=hooks if hooks is not None else HookChain(),
        checkpoint=checkpoint,
        compaction=compaction,
    )


async def drain(gen) -> list:
    """Everything an async iterator yields, up to `limit`."""
    async with asyncio.timeout(5):
        return [event async for event in gen]


async def cancel_mid_turn(agent_, session: Session, user_input: str = "q") -> None:
    """Run a turn in its own task and cancel it once it is blocked."""

    async def consume() -> None:
        async with aclosing(agent_.run(user_input, session=session)) as events:
            async for _ in events:
                pass

    task = asyncio.create_task(consume())
    for _ in range(50):
        await asyncio.sleep(0)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


async def until(predicate, *, what: str) -> None:
    """Let the loop run until `predicate` holds."""
    for _ in range(500):
        if predicate():
            return
        await asyncio.sleep(0)
    raise AssertionError(f"timed out waiting for {what}")


def durable_service(root: Path, *, prefix: str = "c") -> SessionService:
    """A session service over `root` with a fixed clock and ids `c0`, `c1`, ..."""
    ids = iter(f"{prefix}{n}" for n in range(100))
    return SessionService(
        JsonlSessionRepository(root),
        now=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        new_id=lambda: next(ids),
    )


def run_store(
    service: SessionService,
    client,
    *tools: ToolDefinition,
    compaction: CompactionService | None = None,
) -> RunStore:
    """Runs over an agent that checkpoints through `service`, as the server wires it."""
    return RunStore(
        service, loop_agent(client, *tools, checkpoint=service.flush, compaction=compaction)
    )


def skills_at(*roots: Path) -> SkillService:
    """A skill service over test directories, ranked as given; the last is editable."""
    return SkillService(SkillSettings(roots=roots, editable=roots[-1]))


def no_skills() -> SkillService:
    """For call sites with no `tmp_path`: a root that cannot exist."""
    return skills_at(Path("/nonexistent/cell-harness-skills"))


def client_tools() -> ClientToolService:
    """The real declarations, as the server composes them."""
    return ClientToolService(CLIENT_TOOLS)
