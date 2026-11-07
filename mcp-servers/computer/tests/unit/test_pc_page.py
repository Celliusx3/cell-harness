"""The PC image's page script, run against a fake agent-browser."""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).parents[2] / "image" / "pc_page.py"
CDP_FAILURE = "All CDP discovery methods failed for 127.0.0.1:9222: Connection refused"

Step = tuple[str, ...]
Replier = Callable[[Step], str]


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("pc_page", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


pc_page = load_script()


def ok(**data: object) -> str:
    return json.dumps({"success": True, "data": data, "error": None})


def failed(error: str) -> str:
    return json.dumps({"success": False, "data": None, "error": error})


def page_reply(step: Step) -> str:
    replies = {
        ("snapshot",): ok(snapshot='- link "More" [ref=e2]'),
        ("get", "url"): ok(url="https://example.com/"),
        ("get", "title"): ok(title="Example Domain"),
        ("open", "https://example.com"): ok(url="https://example.com/", title="Example Domain"),
    }
    return replies.get(step, ok())


class FakeAgentBrowser:
    """Records each step and answers it with `reply`, as agent-browser --json would."""

    def __init__(self, reply: Replier = page_reply) -> None:
        self.reply = reply
        self.steps: list[Step] = []
        self.cdp_ports: list[str] = []

    def run(self, argv: list[str], **options: object) -> subprocess.CompletedProcess[str]:
        assert argv[:2] == ["agent-browser", "--json"]
        env = options["env"]
        assert isinstance(env, dict)
        self.cdp_ports.append(env["AGENT_BROWSER_CDP"])
        step = tuple(argv[2:])
        self.steps.append(step)
        return subprocess.CompletedProcess(argv, 0, stdout=self.reply(step), stderr="")


@pytest.fixture
def agent(monkeypatch: pytest.MonkeyPatch) -> FakeAgentBrowser:
    fake = FakeAgentBrowser()
    monkeypatch.setattr(pc_page.subprocess, "run", fake.run)
    return fake


def acting(*actions: dict[str, str]) -> str:
    return json.dumps({"actions": list(actions)})


def test_navigate_opens_the_url_and_answers_where_it_landed(agent: FakeAgentBrowser) -> None:
    reply = pc_page.answer(["navigate"], '{"url": "https://example.com"}')

    assert reply == {"ok": True, "url": "https://example.com/", "title": "Example Domain"}
    assert agent.steps == [("open", "https://example.com")]
    assert agent.cdp_ports == ["9222"]


def test_snapshot_is_the_page_as_text_with_its_refs(agent: FakeAgentBrowser) -> None:
    reply = pc_page.answer(["snapshot"], "")

    assert reply == {
        "ok": True,
        "url": "https://example.com/",
        "title": "Example Domain",
        "tree": '- link "More" [ref=e2]',
    }


def test_act_runs_each_action_by_ref_then_reads_the_settled_page(agent: FakeAgentBrowser) -> None:
    stdin = acting(
        {"kind": "fill", "ref": "e4", "text": "bitcoin"},
        {"kind": "type", "ref": "@e4", "text": " price"},
        {"kind": "click", "ref": "e5"},
    )

    reply = pc_page.answer(["act"], stdin)

    assert reply["ok"] is True and reply["completed"] == 3
    assert reply["tree"] == '- link "More" [ref=e2]'
    assert agent.steps[:5] == [
        ("fill", "@e4", "bitcoin"),
        ("type", "@e4", " price"),
        ("click", "@e5"),
        ("wait", "500"),
        ("wait", "--load", "load", "--timeout", "10000"),
    ]


def test_a_page_still_loading_is_read_as_far_as_it_got(agent: FakeAgentBrowser) -> None:
    agent.reply = lambda step: (
        failed("Timeout waiting for load") if "--load" in step else page_reply(step)
    )

    reply = pc_page.answer(["act"], acting({"kind": "click", "ref": "e5"}))

    assert reply["ok"] is True and reply["completed"] == 1


def test_a_ref_from_an_older_read_is_called_stale(agent: FakeAgentBrowser) -> None:
    agent.reply = lambda step: failed("Unknown ref: e2") if step[0] == "click" else page_reply(step)

    reply = pc_page.answer(
        ["act"], acting({"kind": "fill", "ref": "e1", "text": "x"}, {"kind": "click", "ref": "e2"})
    )

    assert reply == {"ok": False, "error": pc_page.STALE_REF, "completed": 1}


def test_chrome_not_up_says_cdp_not_ready_so_the_server_opens_it(agent: FakeAgentBrowser) -> None:
    agent.reply = lambda _: failed(CDP_FAILURE)

    reply = pc_page.answer(["snapshot"], "")

    assert reply == {"ok": False, "error": f"CDP not ready: {CDP_FAILURE}"}


def test_any_other_failure_is_passed_on_in_agent_browsers_words(agent: FakeAgentBrowser) -> None:
    agent.reply = lambda _: failed("net::ERR_NAME_NOT_RESOLVED")

    reply = pc_page.answer(["navigate"], '{"url": "https://nowhere.invalid"}')

    assert reply == {"ok": False, "error": "net::ERR_NAME_NOT_RESOLVED"}


def test_a_step_that_hangs_is_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def hang(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(argv, pc_page.STEP_TIMEOUT_SECONDS)

    monkeypatch.setattr(pc_page.subprocess, "run", hang)

    reply = pc_page.answer(["snapshot"], "")

    assert reply == {"ok": False, "error": "The page did not answer within 20 seconds."}


@pytest.mark.parametrize(
    ("stdout", "error"),
    [
        ("not json", "agent-browser answered with something that is not JSON: 'not json'"),
        ("[]", "agent-browser answered with something that is not an object."),
        (ok(), "agent-browser answered without a text 'snapshot'."),
        (json.dumps({"success": False}), "agent-browser failed."),
    ],
)
def test_an_answer_this_script_cannot_read_is_a_failure(
    agent: FakeAgentBrowser, stdout: str, error: str
) -> None:
    agent.reply = lambda _: stdout

    assert pc_page.answer(["snapshot"], "") == {"ok": False, "error": error}


@pytest.mark.parametrize(
    "stdin",
    [
        "not json",
        "[]",
        "{}",
        '{"actions": []}',
        acting({"kind": "scroll", "ref": "e1"}),
        acting({"kind": "click", "ref": ""}),
        acting({"kind": "click", "ref": "e1", "text": "x"}),
        acting({"kind": "fill", "ref": "e1"}),
        json.dumps({"actions": [{"kind": "fill", "ref": "e1", "text": 3}]}),
        json.dumps({"actions": ["click e1"]}),
    ],
)
def test_act_refuses_arguments_it_cannot_follow_before_any_step(
    agent: FakeAgentBrowser, stdin: str
) -> None:
    reply = pc_page.answer(["act"], stdin)

    assert reply["ok"] is False
    assert agent.steps == []


@pytest.mark.parametrize("argv", [[], ["scroll"], ["snapshot", "extra"]])
def test_an_unknown_command_answers_the_usage(argv: list[str]) -> None:
    assert pc_page.answer(argv, "") == {
        "ok": False,
        "error": "Usage: pc-page navigate|snapshot|act",
    }


def test_main_prints_one_json_reply(
    agent: FakeAgentBrowser, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["pc-page", "snapshot"])
    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))

    pc_page.main()

    assert json.loads(capsys.readouterr().out)["title"] == "Example Domain"
