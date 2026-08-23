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

from harness.agent.events import AgentCompleted, AgentFailed
from harness.agent.loop import LoopAgent
from harness.config.settings import LLMSettings
from harness.llm.adapters.openai import OpenAIClient
from harness.llm.stream import TextChunk
from harness.session.log import Session

SYSTEM_PROMPT = "You are a helpful assistant."


async def _run(prompt: str) -> int:
    """Stream one turn to stdout. Returns the process exit code."""
    settings = LLMSettings()  # type: ignore[call-arg]  # required fields come from env
    agent = LoopAgent(
        name="default",
        model=settings.model,
        client=OpenAIClient(settings),
        system_prompt=SYSTEM_PROMPT,
    )
    session = Session(session_id=str(uuid4()))

    async for event in agent.run(prompt, session=session):
        if isinstance(event, TextChunk):
            # flush per chunk: the point of this command is watching it arrive,
            # and stdout to a pipe is block-buffered by default.
            print(event.text, end="", flush=True)
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
