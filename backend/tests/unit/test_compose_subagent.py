"""`run_subagent` via the composition root: who is offered it, and what a subagent is offered."""

from __future__ import annotations

import json
from contextlib import aclosing
from pathlib import Path

import pytest

from harness.config.sections import McpServer
from harness.config.settings import Settings
from harness.llm.messages import SystemMessage, ToolCall, ToolMessage
from harness.llm.stream import CONTEXT_WINDOW_EXCEEDED, Failed
from harness.mcp.service import McpServerStore
from harness.runtime.service import Runtime
from harness.session.compaction import CompactionEnd
from harness.session.models import TurnStart
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.repository import SessionNotFoundError
from harness.session.service import SessionService
from harness.tools.definition import Ok
from harness.tools.native.code import CODE_PROMPT, LIST
from harness.tools.native.location import LOCATION
from harness.tools.native.question import QUESTION
from harness.tools.native.skills import SKILL_SAVE
from harness.tools.native.subagent import RUN_SUBAGENT
from harness.web import runtime as composition
from harness.web.runtime import build_runtime
from harness.web.server import build_store, build_subagent_logs
from tests.unit.fakes import SteppedClient, calls_tool, completed
from tests.unit.helpers import client_tools, no_bots, no_gate, no_progress, no_skills


@pytest.fixture
def compose(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The real object graph, answering through `client`."""

    def build(client) -> tuple[Runtime, SessionService]:
        monkeypatch.setattr(composition, "OpenAIClient", lambda _settings: client)
        settings = Settings(llm={"model": "m", "api_key": "k"})
        sessions = SessionService(JsonlSessionRepository(tmp_path / "sessions"))
        subagent_logs = SessionService(JsonlSessionRepository(tmp_path / "subagents"))
        mcp = McpServerStore({"stub": McpServer(command="does-not-run")})
        runtime = build_runtime(
            settings,
            sessions,
            mcp,
            no_skills(),
            client_tools(),
            no_gate(),
            bots=no_bots(SessionService(JsonlSessionRepository(tmp_path / "bot-chats"))),
            subagent_logs=subagent_logs,
        )
        return runtime, sessions

    return build


def test_the_bot_is_offered_run_subagent(compose) -> None:
    runtime, _ = compose(SteppedClient(completed("hi")))
    assert runtime.tools is not None

    assert RUN_SUBAGENT in [spec.name for spec in runtime.tools.specs()]


async def test_a_script_cannot_reach_run_subagent(compose) -> None:
    runtime, _ = compose(SteppedClient(completed("hi")))
    assert runtime.tools is not None

    listed = await runtime.tools.execute(
        ToolCall(id="c1", name=LIST, arguments="{}"), progress=no_progress
    )

    assert isinstance(listed, Ok)
    assert RUN_SUBAGENT not in listed.text


async def test_a_subagent_cannot_delegate_ask_or_write_a_skill(compose, tmp_path: Path) -> None:
    tasks = json.dumps({"tasks": [{"name": "aapl", "task": "Look up AAPL."}]})
    client = SteppedClient(
        calls_tool(RUN_SUBAGENT, tasks, id="c1"),
        completed("AAPL grew 2%."),
        completed("Apple grew 2%."),
    )
    runtime, sessions = compose(client)
    session = await sessions.create()

    async with aclosing(runtime.run("compare", session=session)) as events:
        async for _ in events:
            pass

    subagent_tools = {spec.name for spec in client.seen_tools_per_call[1] or []}
    assert subagent_tools.isdisjoint({RUN_SUBAGENT, QUESTION, LOCATION, SKILL_SAVE})
    subagent_system = client.seen_per_call[1][0]
    assert isinstance(subagent_system, SystemMessage)
    assert CODE_PROMPT.strip() in subagent_system.content
    assert (tmp_path / "subagents" / "c1.0.jsonl").exists()


async def test_a_subagent_that_overflows_compacts_like_the_bot_and_answers(
    compose, tmp_path: Path
) -> None:
    tasks = json.dumps({"tasks": [{"name": "aapl", "task": "Look up AAPL."}]})
    overflow = [
        Failed(
            reason="provider sent an error: Context length exceeded", code=CONTEXT_WINDOW_EXCEEDED
        )
    ]
    client = SteppedClient(
        calls_tool(RUN_SUBAGENT, tasks, id="c1"),
        overflow,
        completed("The task is to look up AAPL."),
        completed("AAPL grew 2%."),
        completed("Apple grew 2%."),
    )
    runtime, sessions = compose(client)
    session = await sessions.create()

    async with aclosing(runtime.run("compare", session=session)) as events:
        async for _ in events:
            pass

    returned = [m for m in client.seen_per_call[-1] if isinstance(m, ToolMessage)]
    assert "## aapl\nAAPL grew 2%." in returned[0].content[0].text
    subagent_log = await SessionService(JsonlSessionRepository(tmp_path / "subagents")).read("c1.0")
    ends = [e for e in subagent_log.events() if isinstance(e, CompactionEnd)]
    assert [end.succeeded for end in ends] == [True]


class _LogWatcher(SteppedClient):
    """Records, at each request, whether the subagent's log is already on disk."""

    def __init__(self, log: Path, *scripts) -> None:
        super().__init__(*scripts)
        self._log = log
        self.log_on_disk: list[bool] = []

    async def stream_completion(self, messages, model, *, tools=None):
        self.log_on_disk.append(self._log.exists())
        async for event in super().stream_completion(messages, model, tools=tools):
            yield event


async def test_a_subagents_log_is_saved_before_its_first_request(compose, tmp_path: Path) -> None:
    tasks = json.dumps({"tasks": [{"name": "aapl", "task": "Look up AAPL."}]})
    client = _LogWatcher(
        tmp_path / "subagents" / "c1.0.jsonl",
        calls_tool(RUN_SUBAGENT, tasks, id="c1"),
        completed("AAPL grew 2%."),
        completed("Apple grew 2%."),
    )
    runtime, sessions = compose(client)
    session = await sessions.create()

    async with aclosing(runtime.run("compare", session=session)) as events:
        async for _ in events:
            pass

    assert client.log_on_disk == [False, True, True]


async def test_subagent_logs_sit_beside_the_conversations_and_are_not_among_them(
    tmp_path: Path,
) -> None:
    settings = Settings(
        llm={"model": "m", "api_key": "k"}, sessions={"root": tmp_path / "sessions"}
    )
    logs = build_subagent_logs(settings)
    log = await logs.create("c1.0")
    log.append(TurnStart(turn=0))
    await logs.flush(log)

    assert (tmp_path / "subagents" / "c1.0.jsonl").exists()
    with pytest.raises(SessionNotFoundError):
        await build_store(settings).read("c1.0")
