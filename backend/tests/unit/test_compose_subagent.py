"""`run_subagent` via the composition root: who is offered it, and what a subagent is offered."""

from __future__ import annotations

import json
from contextlib import aclosing
from pathlib import Path

import pytest

from harness.config.sections import McpServer
from harness.config.settings import Settings
from harness.llm import (
    CONTEXT_WINDOW_EXCEEDED,
    Failed,
    SystemMessage,
    ToolCall,
    ToolMessage,
    UserMessage,
)
from harness.mcp.service import McpService
from harness.prompts import CODE_PROMPT
from harness.runtime.service import Runtime
from harness.session.compaction import CompactionEnd
from harness.session.models import TurnStart
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.repository import SessionNotFoundError
from harness.session.service import SessionService
from harness.skills import SKILL, SkillService
from harness.tools import Ok
from harness.tools.native.code_mode import LIST_FUNCTIONS
from harness.tools.native.location import GET_LOCATION
from harness.tools.native.question import ASK_USER
from harness.tools.native.skills import SKILL_SAVE
from harness.tools.native.subagent import RUN_SUBAGENT
from harness.web import runtime as composition
from harness.web.runtime import build_runtime
from harness.web.server import build_store, build_subagent_logs
from tests.unit.fakes import SteppedClient, calls_tool, completed
from tests.unit.helpers import (
    ORIGIN,
    client_tools,
    new_session,
    no_approvals,
    no_bots,
    no_progress,
    no_skills,
    skills_at,
)
from tests.webapp import files_in, images_in, secrets_with_default_model


@pytest.fixture
def compose(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The real object graph, answering through `client`."""

    def build(client, skills: SkillService | None = None) -> tuple[Runtime, SessionService]:
        monkeypatch.setattr(composition, "OpenAIClient", lambda _settings, read_image: client)
        settings = Settings(
            local_settings_path=tmp_path / "config.local.json", llm={"model": "m", "api_key": "k"}
        )
        sessions = SessionService(JsonlSessionRepository(tmp_path / "sessions"))
        subagent_logs = SessionService(JsonlSessionRepository(tmp_path / "subagents"))
        mcp = McpService({"stub": McpServer(command="does-not-run")})
        runtime = build_runtime(
            settings,
            sessions,
            mcp,
            skills if skills is not None else no_skills(),
            client_tools(),
            no_approvals(),
            bots=no_bots(SessionService(JsonlSessionRepository(tmp_path / "bot-chats"))),
            subagent_logs=subagent_logs,
            secrets=secrets_with_default_model(tmp_path),
            images=images_in(tmp_path),
            files=files_in(tmp_path),
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
        ToolCall(id="c1", name=LIST_FUNCTIONS, arguments="{}"),
        progress=no_progress,
        origin=ORIGIN,
        session=new_session(),
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

    async with aclosing(runtime.run("compare", session=session, bot_id="b")) as events:
        async for _ in events:
            pass

    subagent_tools = {spec.name for spec in client.seen_tools_per_call[1] or []}
    assert subagent_tools.isdisjoint({RUN_SUBAGENT, ASK_USER, GET_LOCATION, SKILL_SAVE})
    subagent_system = client.seen_per_call[1][0]
    assert isinstance(subagent_system, SystemMessage)
    assert CODE_PROMPT.strip() in subagent_system.content
    assert (tmp_path / "subagents" / "c1.0.jsonl").exists()


async def test_a_subagent_is_told_it_is_a_helper_ahead_of_code_mode(compose) -> None:
    tasks = json.dumps({"tasks": [{"name": "aapl", "task": "Look up AAPL."}]})
    client = SteppedClient(
        calls_tool(RUN_SUBAGENT, tasks, id="c1"),
        completed("AAPL grew 2%."),
        completed("Apple grew 2%."),
    )
    runtime, sessions = compose(client)
    session = await sessions.create()

    async with aclosing(runtime.run("compare", session=session, bot_id="b")) as events:
        async for _ in events:
            pass

    assert client.seen_per_call[1][0] == SystemMessage(
        content="You are a helper named aapl, started by the main assistant to do one task as "
        "part of its answer to the user. Nobody will read your questions, so do not ask any: do "
        "the task with your tools, then reply with a short result. That reply is all the main "
        "assistant receives." + CODE_PROMPT
    )


async def test_a_subagent_is_shown_the_skills_it_may_load(compose, tmp_path: Path) -> None:
    root = tmp_path / "skills"
    (root / "pdf").mkdir(parents=True)
    (root / "pdf" / "SKILL.md").write_text("---\ndescription: PDF work.\n---\nDo it.\n")
    tasks = json.dumps({"tasks": [{"name": "aapl", "task": "Look up AAPL."}]})
    client = SteppedClient(
        calls_tool(RUN_SUBAGENT, tasks, id="c1"),
        completed("AAPL grew 2%."),
        completed("Apple grew 2%."),
    )
    runtime, sessions = compose(client, skills_at(root))
    session = await sessions.create()

    async with aclosing(runtime.run("compare", session=session, bot_id="b")) as events:
        async for _ in events:
            pass

    assert SKILL in {spec.name for spec in client.seen_tools_per_call[1] or []}
    subagent_task = client.seen_per_call[1][1]
    assert isinstance(subagent_task, UserMessage)
    assert subagent_task.content.startswith("Look up AAPL.\n\n<system-reminder>\n")
    assert "\n- pdf: PDF work.\n</system-reminder>" in subagent_task.content
    logged = [e.model_dump(mode="json") for e in session.events()]
    assert "<system-reminder>" not in json.dumps(logged)


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

    async with aclosing(runtime.run("compare", session=session, bot_id="b")) as events:
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

    async with aclosing(runtime.run("compare", session=session, bot_id="b")) as events:
        async for _ in events:
            pass

    assert client.log_on_disk == [False, True, True]


async def test_subagent_logs_sit_beside_the_conversations_and_are_not_among_them(
    tmp_path: Path,
) -> None:
    settings = Settings(
        local_settings_path=tmp_path / "config.local.json",
        llm={"model": "m", "api_key": "k"},
        sessions={"root": tmp_path / "sessions"},
    )
    logs = build_subagent_logs(settings)
    log = await logs.create("c1.0")
    log.append(TurnStart(turn=0))
    await logs.flush(log)

    assert (tmp_path / "subagents" / "c1.0.jsonl").exists()
    with pytest.raises(SessionNotFoundError):
        await build_store(settings).read("c1.0")
