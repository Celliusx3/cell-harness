"""`harness run "<prompt>"` — a driver, not an interface.

It exists so a human can feel the loop working. It deliberately has no config, no
session management, and no argument parsing beyond a prompt: conversations arrive
in phase 3 and the browser in phase 4. If this file passes ~60 lines it is
absorbing something that belongs elsewhere.

**No HTTP here, and none before phase 4.** The obvious quick endpoint streams on
the request connection, which is precisely the design phase 4 exists to undo — a
turn must outlive the tab that started it.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from uuid import uuid4

from harness.agent.events import AgentCompleted, AgentFailed, ToolProgress, ToolResult
from harness.agent.loop import LoopAgent
from harness.config.settings import LLMSettings
from harness.llm.adapters.openai import OpenAIClient
from harness.llm.stream import TextChunk, ToolCallChunk
from harness.session.log import Session
from harness.tools.native.clock import clock_tool
from harness.tools.pipeline import ToolPipeline
from harness.tools.registry import ToolRegistry

SYSTEM_PROMPT = (
    "You are a helpful assistant. When a tool can answer the user's question, "
    "call it instead of guessing."
)


def build_agent(settings: LLMSettings) -> LoopAgent:
    """The composition root: everything wired in one place, in a known order.

    This is what stands in for dsh's config-driven plugin tree. A missing
    dependency is a TypeError here rather than a runtime surprise, which is the
    whole reason we do not need an injection framework.
    """
    registry = ToolRegistry([clock_tool()])
    return LoopAgent(
        name="default",
        model=settings.model,
        client=OpenAIClient(settings),
        tools=ToolPipeline(registry),
        system_prompt=SYSTEM_PROMPT,
    )


async def _run(prompt: str) -> int:
    """Stream one turn to stdout. Returns the process exit code."""
    settings = LLMSettings()  # type: ignore[call-arg]  # required fields come from env
    agent = build_agent(settings)
    session = Session(session_id=str(uuid4()))

    async for event in agent.run(prompt, session=session):
        if isinstance(event, TextChunk):
            # flush per chunk: the point of this command is watching it arrive,
            # and stdout to a pipe is block-buffered by default.
            print(event.text, end="", flush=True)
        elif isinstance(event, ToolCallChunk):
            # stderr, so piping stdout gives the answer alone.
            print(f"\n  → {event.call.name}({event.call.arguments})", file=sys.stderr, flush=True)
        elif isinstance(event, ToolProgress):
            # `percent` is None when the total is not knowable, which is the
            # common case — so the label has to read correctly without it.
            percent = f"{event.percent:.0f}% " if event.percent is not None else ""
            print(f"    … {percent}{event.message or ''}".rstrip(), file=sys.stderr, flush=True)
        elif isinstance(event, ToolResult):
            print(f"  ← {event.content}", file=sys.stderr, flush=True)
        elif isinstance(event, AgentCompleted):
            print()
            return 0
        elif isinstance(event, AgentFailed):
            print(f"\nerror: {event.reason}", file=sys.stderr)
            return 1
    # Unreachable while the loop keeps its contract; reported rather than
    # returning 0, because a silent success here would hide a broken one.
    print("\nerror: agent produced no terminal event", file=sys.stderr)
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(prog="harness")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run one turn and print the reply")
    run.add_argument("prompt")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(args.prompt)))


if __name__ == "__main__":
    main()
