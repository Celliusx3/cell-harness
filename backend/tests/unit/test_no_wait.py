"""The orchestrator may not wait in its own turn; its workers and helpers may."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.config.settings import Settings
from harness.mcp import McpService
from harness.prompts import CODE_PROMPT, NO_WAIT_REFUSAL, ORCHESTRATOR
from harness.runtime.hooks.calls import Signature
from harness.runtime.hooks.native.no_wait import NoWaitHook, waits
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.web.runtime import SUBAGENT_TOOLS, build_runtime, helper_runtime
from harness.web.tickets_wiring import WORKER_TOOLS
from tests.unit.helpers import client_tools, no_approvals, no_bots, no_skills
from tests.webapp import files_in, images_in, secrets_in


def script(code: str) -> str:
    return json.dumps({"code": code})


@pytest.mark.parametrize(
    ("name", "arguments", "expected"),
    [
        ("execute_typescript", script("await new Promise(r => setTimeout(r, 5000));"), True),
        ("execute_typescript", script("setTimeout(done, 60000)"), True),
        ("execute_typescript", script("await sleep(10)"), False),
        ("execute_typescript", script('const app = "sleep tracker"; return app;'), False),
        ("execute_typescript", script("setTimeout(done, 4999)"), False),
        ("execute_typescript", script("const sleeper = await fs__read_file({})"), False),
        ("computer__shell", json.dumps({"command": "sleep 30 && ls"}), True),
        ("computer__shell", json.dumps({"command": "ls ~/sleepy"}), False),
        ("computer__shell", json.dumps({"command": "cd app && sleep 5; ls"}), True),
        ("computer__shell", json.dumps({"command": "(sleep 2) | cat"}), True),
        ("computer__shell", json.dumps({"command": "echo 'sleep tracker'"}), False),
        ("computer__shell", json.dumps({"command": "grep sleep notes.txt"}), False),
        ("fs__read_file", json.dumps({"path": "sleep"}), False),
        ("execute_typescript", "not json", False),
    ],
)
def test_a_call_waits_when_its_script_or_command_sleeps_or_times_out_long(
    name: str, arguments: str, expected: bool
) -> None:
    assert waits(name, arguments) is expected


async def test_the_hook_refuses_a_waiting_call_with_its_reason() -> None:
    hook = NoWaitHook()
    waiting = Signature(name="execute_typescript", args=script("setTimeout(go, 9000)"))
    working = Signature(name="execute_typescript", args=script("return 1"))

    assert await hook.pre(waiting, ()) == NO_WAIT_REFUSAL
    assert await hook.pre(working, ()) is None


def test_only_the_bots_own_runtime_routes_and_refuses_waits(tmp_path: Path) -> None:
    runtime = build_runtime(
        Settings(),
        SessionService(JsonlSessionRepository(tmp_path)),
        McpService({}),
        no_skills(),
        client_tools(),
        no_approvals(),
        bots=no_bots(SessionService(JsonlSessionRepository(tmp_path / "bot-chats"))),
        subagent_logs=SessionService(JsonlSessionRepository(tmp_path / "subagents")),
        secrets=secrets_in(tmp_path),
        images=images_in(tmp_path),
        files=files_in(tmp_path),
    )
    assert runtime.tools is not None
    helpers = [
        helper_runtime(runtime.tools.tool_service, runtime, tools)
        for tools in (SUBAGENT_TOOLS, WORKER_TOOLS)
    ]

    assert runtime.guidance.startswith(ORCHESTRATOR)
    assert any(isinstance(hook, NoWaitHook) for hook in runtime.hooks.tool_hooks)
    for helper in helpers:
        assert helper.guidance == CODE_PROMPT
        assert not any(isinstance(hook, NoWaitHook) for hook in helper.hooks.tool_hooks)
        assert len(helper.hooks.tool_hooks) == len(runtime.hooks.tool_hooks) - 1
