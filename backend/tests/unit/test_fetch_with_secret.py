"""`fetch_with_secret`: a key goes to its site for a bot allowed it; no failure shows it."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from harness.bots import ASSISTANT_ID, BUILDER_ID, BotService
from harness.secrets import Destination, SecretService
from harness.tools import Failure, Ok, ToolOutcome
from harness.tools.native.secrets import ASK_FOR_SECRET, FETCH_WITH_SECRET, fetch_with_secret_tool
from harness.tools.native.secrets.tools import (
    NO_SECRET,
    NOT_ALLOWED,
    REDIRECTED,
    REQUEST_FAILED,
    TOO_LARGE,
    WRONG_ORIGIN,
)
from harness.web.runtime import DEFAULT_TOOLS, NOT_CALLABLE_FROM_SCRIPTS, SUBAGENT_TOOLS
from tests.unit.helpers import context_for, durable_service
from tests.webapp import bots_in, secrets_in

CONFIG = Path(__file__).resolve().parents[2] / "config.json"
BOT = ASSISTANT_ID
KEY = "tok-9Zx=7Lm/q+Abc"
LEAK = "LEAKED-Q7xZ"
GITHUB = Destination(origin="https://api.github.com", auth="bearer")
NOTION = Destination(origin="https://api.notion.com", auth="header", header_name="X-Api-Key")
NOTIFICATIONS = {"name": "github", "url": "https://api.github.com/notifications", "method": "GET"}
ISSUES = {"name": "github", "url": "https://api.github.com/repos/o/r/issues", "method": "POST"}

Handler = Callable[[httpx.Request], httpx.Response]


def _answers_ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, text="{}")


def _keyring(
    tmp_path: Path, saved: Destination = GITHUB, saved_name: str = "github"
) -> tuple[SecretService, BotService]:
    secrets = secrets_in(tmp_path)
    secrets.save(saved_name, saved, SecretStr(KEY))
    bots = bots_in(tmp_path, durable_service(tmp_path / "sessions"))
    bots.allow_secret(BOT, saved_name)
    return secrets, bots


async def _fetch(
    tmp_path: Path,
    arguments: dict,
    handler: Handler = _answers_ok,
    saved: Destination = GITHUB,
    saved_name: str = "github",
    bot_id: str = BOT,
) -> tuple[ToolOutcome, list[httpx.Request]]:
    secrets, bots = _keyring(tmp_path, saved, saved_name)
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    tool = fetch_with_secret_tool(secrets, bots, httpx.MockTransport(record))
    outcome = await tool.invoke(json.dumps(arguments), context=context_for(bot_id=bot_id))
    return outcome, seen


async def test_a_name_with_no_saved_key_says_to_ask_for_one_and_sends_nothing(tmp_path) -> None:
    outcome, seen = await _fetch(tmp_path, {**NOTIFICATIONS, "name": "linear"})

    assert isinstance(outcome, Failure)
    assert outcome.code == NO_SECRET
    assert "call ask_for_secret first" in outcome.message
    assert seen == []


@pytest.mark.parametrize("bot_id", [BUILDER_ID, "gone"], ids=["another bot", "no such bot"])
async def test_a_bot_not_allowed_the_key_is_refused_and_nothing_is_sent(
    tmp_path, bot_id: str
) -> None:
    outcome, seen = await _fetch(tmp_path, NOTIFICATIONS, bot_id=bot_id)

    assert isinstance(outcome, Failure)
    assert outcome.code == NOT_ALLOWED
    assert "may not use 'github'" in outcome.message
    assert seen == []


async def test_header_auth_sends_the_key_in_its_header_and_no_authorization(tmp_path) -> None:
    arguments = {"name": "notion", "url": "https://api.notion.com/v1/users", "method": "GET"}

    outcome, seen = await _fetch(tmp_path, arguments, saved=NOTION, saved_name="notion")

    assert isinstance(outcome, Ok)
    (request,) = seen
    assert request.headers["X-Api-Key"] == KEY
    assert "authorization" not in request.headers


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/notifications",
        "https://api.github.com.evil.example/notifications",
        "https://api.github.com:8443/notifications",
        "http://api.github.com/notifications",
        "https://user:pw@api.github.com/notifications",
    ],
    ids=["another host", "a longer host", "another port", "plain http", "userinfo"],
)
async def test_a_url_off_the_saved_origin_is_refused_and_nothing_is_sent(tmp_path, url) -> None:
    outcome, seen = await _fetch(tmp_path, {**NOTIFICATIONS, "url": url})

    assert isinstance(outcome, Failure)
    assert outcome.code == WRONG_ORIGIN
    assert seen == []


async def test_a_redirect_is_a_failure_and_its_location_is_never_requested(tmp_path) -> None:
    def moved(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "https://evil.example/collect"})

    outcome, seen = await _fetch(tmp_path, NOTIFICATIONS, moved)

    assert isinstance(outcome, Failure)
    assert outcome.code == REDIRECTED
    assert [str(request.url) for request in seen] == [NOTIFICATIONS["url"]]


async def test_a_body_over_1_mib_is_a_failure_that_shows_none_of_it(tmp_path) -> None:
    def huge(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=LEAK + "x" * (1024 * 1024))

    outcome, _ = await _fetch(tmp_path, NOTIFICATIONS, huge)

    assert isinstance(outcome, Failure)
    assert outcome.code == TOO_LARGE
    assert LEAK not in outcome.message


async def test_a_transport_error_is_a_failure_that_does_not_show_the_key(tmp_path) -> None:
    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"could not send Bearer {KEY}", request=request)

    outcome, _ = await _fetch(tmp_path, NOTIFICATIONS, unreachable)

    assert isinstance(outcome, Failure)
    assert outcome.code == REQUEST_FAILED
    assert KEY not in outcome.message


@pytest.mark.parametrize("body", [{"title": "Bug", "labels": ["a"]}, {}, ["a", 1]])
async def test_a_body_the_model_sends_as_json_is_sent_as_json(tmp_path, body: object) -> None:
    outcome, seen = await _fetch(tmp_path, {**ISSUES, "body": body})

    assert isinstance(outcome, Ok)
    (request,) = seen
    assert json.loads(request.content) == body
    assert request.headers["Content-Type"] == "application/json"


async def test_a_call_without_a_body_sends_none(tmp_path) -> None:
    outcome, seen = await _fetch(tmp_path, NOTIFICATIONS)

    assert isinstance(outcome, Ok)
    (request,) = seen
    assert request.content == b""
    assert "Content-Type" not in request.headers


class _ClosingCountTransport(httpx.MockTransport):
    def __init__(self) -> None:
        super().__init__(_answers_ok)
        self.closes = 0

    async def aclose(self) -> None:
        self.closes += 1


async def test_each_fetch_closes_its_client(tmp_path) -> None:
    secrets, bots = _keyring(tmp_path)
    transport = _ClosingCountTransport()
    tool = fetch_with_secret_tool(secrets, bots, transport)

    for _ in range(2):
        outcome = await tool.invoke(json.dumps(NOTIFICATIONS), context=context_for(bot_id=BOT))
        assert isinstance(outcome, Ok)

    assert transport.closes == 2


def test_the_main_chat_is_offered_fetch_and_scripts_and_helpers_are_not() -> None:
    assert FETCH_WITH_SECRET in DEFAULT_TOOLS
    assert FETCH_WITH_SECRET in NOT_CALLABLE_FROM_SCRIPTS
    assert FETCH_WITH_SECRET not in SUBAGENT_TOOLS


def test_the_main_chat_is_offered_the_key_card_and_scripts_are_not() -> None:
    assert ASK_FOR_SECRET in DEFAULT_TOOLS
    assert ASK_FOR_SECRET in NOT_CALLABLE_FROM_SCRIPTS


def test_the_committed_config_asks_before_a_saved_key_is_sent() -> None:
    committed = json.loads(CONFIG.read_text())

    assert FETCH_WITH_SECRET in committed["approval"]["tools"]
