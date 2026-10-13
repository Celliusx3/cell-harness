"""Rakazo's page script: what goes over stdin, what comes back, and Chrome not being up."""

from __future__ import annotations

import json
from collections.abc import Sequence

import pytest

from computer.browser import Browser, BrowserError
from computer.docker import CommandResult, DockerError, DockerTimeout
from computer.models import Action
from tests.conftest import (
    ACTED,
    CDP_DOWN,
    NAME,
    NAVIGATED,
    SNAPSHOT,
    STALE_REF_REPLY,
    FakeDocker,
    TickingClock,
)


def browser(docker: FakeDocker) -> Browser:
    return Browser(docker=docker, container=NAME, clock=TickingClock().clock)


def page_command(command: str) -> list[str]:
    return ["exec", "-i", "-e", "RAKAZO_BROWSER_ARGS_STDIN=1", NAME, "rakazo-page-browser", command]


async def test_navigate_sends_the_url_on_stdin_as_one_json_line() -> None:
    docker = FakeDocker(status="running", page_replies=[NAVIGATED])

    opened = await browser(docker).navigate("https://example.com")

    assert docker.calls == [page_command("navigate")]
    assert docker.stdins[0].endswith("\n")
    assert docker.stdins[0].count("\n") == 1
    assert json.loads(docker.stdins[0]) == {"url": "https://example.com"}
    assert (opened.url, opened.title) == ("https://example.com/", "Example Domain")


async def test_reading_returns_the_tree_as_content_and_drops_the_elements() -> None:
    docker = FakeDocker(status="running", page_replies=[SNAPSHOT])

    page = await browser(docker).read()

    assert docker.calls == [page_command("snapshot")]
    assert json.loads(docker.stdins[0]) == {}
    assert page.content.startswith("Example Domain\n- link")
    assert set(page.model_dump()) == {"url", "title", "content"}


async def test_acting_sends_the_actions_and_no_text_for_a_click() -> None:
    docker = FakeDocker(status="running", page_replies=[ACTED])
    actions = [Action(kind="click", ref="e1"), Action(kind="fill", ref="e2", text="hi")]

    acted = await browser(docker).act(actions)

    assert docker.calls == [page_command("act")]
    assert json.loads(docker.stdins[0]) == {
        "actions": [{"kind": "click", "ref": "e1"}, {"kind": "fill", "ref": "e2", "text": "hi"}]
    }
    assert acted.actions_completed == 2
    assert acted.content.startswith("Example Domain")


async def test_every_page_command_has_a_25_second_timeout() -> None:
    docker = FakeDocker(status="running", page_replies=[SNAPSHOT])

    await browser(docker).read()

    assert docker.timeouts == [25]


async def test_a_stale_ref_says_how_many_completed_and_to_read_the_page_again() -> None:
    docker = FakeDocker(status="running", page_replies=[STALE_REF_REPLY])

    with pytest.raises(BrowserError) as caught:
        await browser(docker).act([Action(kind="click", ref="e1"), Action(kind="click", ref="e2")])

    message = str(caught.value)
    assert message.startswith("0 of 2 actions completed")
    assert "Stale element ref" in message
    assert "may have taken effect" not in message
    assert message.endswith("Call browser_read_page before going on.")
    assert "fallback" not in message
    assert "computer_act" not in message


async def test_an_uncertain_failure_says_the_failed_action_may_have_taken_effect() -> None:
    uncertain = json.dumps(
        {"ok": False, "completed": 1, "uncertain": True, "error": "Click timed out."}
    )
    docker = FakeDocker(status="running", page_replies=[uncertain])

    with pytest.raises(BrowserError, match="1 of 2 actions completed") as caught:
        await browser(docker).act([Action(kind="click", ref="e1"), Action(kind="click", ref="e2")])

    assert "may have taken effect" in str(caught.value)


@pytest.mark.parametrize(
    ("call", "reply"),
    [
        ("navigate", json.dumps({"ok": False, "error": "net::ERR_NAME_NOT_RESOLVED"})),
        ("read", STALE_REF_REPLY),
    ],
)
async def test_a_failed_page_command_carries_the_scripts_error_and_nothing_else(
    call: str, reply: str
) -> None:
    docker = FakeDocker(status="running", page_replies=[reply])
    page = browser(docker)

    with pytest.raises(BrowserError) as caught:
        await (page.navigate("https://nowhere.invalid") if call == "navigate" else page.read())

    assert json.loads(reply)["error"] in str(caught.value)
    assert "fallback" not in str(caught.value)
    assert "computer_act" not in str(caught.value)


async def test_chrome_not_up_is_launched_once_and_the_command_retried_until_it_works() -> None:
    docker = FakeDocker(status="running", page_replies=[CDP_DOWN, CDP_DOWN, CDP_DOWN, NAVIGATED])

    opened = await browser(docker).navigate("https://example.com")

    assert opened.title == "Example Domain"
    assert docker.launches() == [["exec", "-d", NAME, "rakazo-focus-or-launch", "rakazo-browser"]]
    assert [call for call in docker.calls if call[:2] == ["exec", "-i"]] == [
        page_command("navigate")
    ] * 4


async def test_chrome_that_never_comes_up_fails_after_15_seconds() -> None:
    docker = FakeDocker(status="running", page_replies=[CDP_DOWN])
    ticking = TickingClock()

    with pytest.raises(BrowserError, match="did not start within 15 seconds"):
        await Browser(docker=docker, container=NAME, clock=ticking.clock).read()

    assert len(docker.launches()) == 1
    assert 15 <= ticking.now < 16


async def test_a_page_that_does_not_answer_in_time_says_so() -> None:
    class Hanging(FakeDocker):
        async def run(
            self, args: Sequence[str], *, stdin: str, timeout_seconds: float
        ) -> CommandResult:
            raise DockerTimeout("docker exec did not finish within 25 seconds")

    with pytest.raises(BrowserError, match="did not answer within 25 seconds"):
        await browser(Hanging(status="running")).read()


async def test_a_page_script_that_exits_non_zero_is_a_docker_error() -> None:
    docker = FakeDocker(status="running")
    docker.refused_verbs.add("exec")

    with pytest.raises(DockerError, match="rakazo-page-browser snapshot failed"):
        await browser(docker).read()


@pytest.mark.parametrize(
    ("call", "reply"),
    [
        ("navigate", "not json at all"),
        ("navigate", json.dumps({"ok": True, "url": "https://example.com/"})),
        ("read", json.dumps({"ok": True, "url": "u", "title": "t"})),
        ("read", json.dumps({"url": "u", "title": "t", "tree": "x"})),
        ("act", json.dumps({**json.loads(SNAPSHOT)})),
        ("act", json.dumps({"ok": False})),
    ],
)
async def test_a_malformed_reply_fails_closed(call: str, reply: str) -> None:
    page = browser(FakeDocker(status="running", page_replies=[reply]))

    with pytest.raises(BrowserError, match="cannot read"):
        if call == "navigate":
            await page.navigate("https://example.com")
        elif call == "read":
            await page.read()
        else:
            await page.act([Action(kind="click", ref="e1")])
