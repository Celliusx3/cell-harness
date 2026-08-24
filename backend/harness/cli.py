"""`harness run` / `list` / `resume` — a driver, not an interface.

It exists so a human can feel the harness working. It deliberately has no session
management beyond naming an id: the browser arrives at phase 4, and everything a
UI needs lives in `SessionService`, not here.

Settings are loaded once, here, and handed down — see `harness.config`.

**No HTTP here, and none before phase 4.** The obvious quick endpoint streams on
the request connection, which is precisely the design phase 4 exists to undo — a
turn must outlive the tab that started it.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from harness.agent.events import AgentCompleted, AgentFailed, ToolProgress, ToolResult
from harness.agent.loop import LoopAgent
from harness.config.settings import MissingConfigError, Settings, load
from harness.llm.adapters.openai import OpenAIClient
from harness.llm.stream import TextChunk, ToolCallChunk
from harness.session.log import Session
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.repository import (
    SessionCorruptionError,
    SessionFormatUnsupportedError,
    SessionNotFoundError,
)
from harness.session.service import SessionService
from harness.tools.native.clock import clock_tool
from harness.tools.pipeline import ToolPipeline
from harness.tools.registry import ToolRegistry

SYSTEM_PROMPT = (
    "You are a helpful assistant. When a tool can answer the user's question, "
    "call it instead of guessing."
)


def build_store(settings: Settings) -> SessionService:
    return SessionService(JsonlSessionRepository(settings.sessions.root))


def build_agent(settings: Settings, store: SessionService) -> LoopAgent:
    """The composition root: everything wired in one place, in a known order.

    This is what stands in for dsh's config-driven plugin tree. A missing
    dependency is a TypeError here rather than a runtime surprise, which is the
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


async def _drive(agent: LoopAgent, session: Session, prompt: str, store: SessionService) -> int:
    """Stream one turn to stdout. Returns the process exit code."""
    code = 1
    try:
        async for event in agent.run(prompt, session=session):
            if isinstance(event, TextChunk):
                # flush per chunk: the point of this command is watching it
                # arrive, and stdout to a pipe is block-buffered by default.
                print(event.text, end="", flush=True)
            elif isinstance(event, ToolCallChunk):
                # stderr, so piping stdout gives the answer alone.
                print(
                    f"\n  → {event.call.name}({event.call.arguments})", file=sys.stderr, flush=True
                )
            elif isinstance(event, ToolProgress):
                # `percent` is None when the total is not knowable, which is the
                # common case — so the label has to read correctly without it.
                percent = f"{event.percent:.0f}% " if event.percent is not None else ""
                print(f"    … {percent}{event.message or ''}".rstrip(), file=sys.stderr, flush=True)
            elif isinstance(event, ToolResult):
                print(f"  ← {event.content}", file=sys.stderr, flush=True)
            elif isinstance(event, AgentCompleted):
                print()
                code = 0
            elif isinstance(event, AgentFailed):
                print(f"\nerror: {event.reason}", file=sys.stderr)
                code = 1
    finally:
        # The turn's own checkpoints all happen *before* work, so the last
        # response is not yet durable when the loop ends. Without this a
        # completed conversation would wait for a request that never comes; on
        # the failure paths it is what makes the partial turn resumable.
        await store.flush(session)
    return code


async def _run(prompt: str) -> int:
    settings = load()
    store = build_store(settings)
    agent = build_agent(settings, store)
    session = await store.create()
    # stderr, so it does not pollute a piped answer — but visible, because it is
    # the id `resume` needs.
    print(f"session {session.id}", file=sys.stderr)
    return await _drive(agent, session, prompt, store)


async def _resume(session_id: str, prompt: str) -> int:
    settings = load()
    store = build_store(settings)
    agent = build_agent(settings, store)
    try:
        session = await store.resume(session_id)
    except (SessionNotFoundError, SessionCorruptionError, SessionFormatUnsupportedError) as err:
        # These carry the detail that makes them actionable — the path, the
        # version, the line number — so they are reported in full.
        print(f"error: {err}", file=sys.stderr)
        return 1
    return await _drive(agent, session, prompt, store)


async def _list() -> int:
    for header in await build_store(Settings()).list():
        when = header.created_at.astimezone().strftime("%Y-%m-%d %H:%M")
        print(f"{header.id}  {when}  {header.title}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="harness")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run one turn in a new conversation")
    run.add_argument("prompt")

    sub.add_parser("list", help="list stored conversations, newest first")

    resume = sub.add_parser("resume", help="continue a stored conversation")
    resume.add_argument("session_id")
    resume.add_argument("prompt")

    args = parser.parse_args()
    try:
        if args.command == "list":
            raise SystemExit(asyncio.run(_list()))
        if args.command == "resume":
            raise SystemExit(asyncio.run(_resume(args.session_id, args.prompt)))
        raise SystemExit(asyncio.run(_run(args.prompt)))
    except MissingConfigError as err:
        # Names the file to edit. A traceback here would bury the one sentence
        # that tells a new user what to do.
        print(f"error: {err}", file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
