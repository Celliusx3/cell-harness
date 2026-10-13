"""A tool result's relay entry: rewritten to a relay when loopback, dropped otherwise."""

from __future__ import annotations

import logging

import pytest
from mcp.types import CallToolResult, TextContent

from harness.mcp.relay import RELAY_TTL_SECONDS, Relays, Upstream, with_relay_url

RELAY_META = "io.cell-harness/relay"
PAGE = "/embed.html?path=websockify%3Ftoken%3DZk3_q-9x&view_only=1"


class Now:
    """Time that moves only when a test moves it."""

    def __init__(self) -> None:
        self.seconds = 1000.0

    def __call__(self) -> float:
        return self.seconds


def result_with(meta: dict[str, object] | None) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text="{}")], _meta=meta)


def relay_id_of(url: str) -> str:
    return url.removeprefix("/api/relay/").split("/", 1)[0]


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost"])
def test_a_loopback_entry_becomes_a_relay_url_with_the_same_path_and_query(host: str) -> None:
    relays = Relays(now=Now())

    rewritten = with_relay_url(
        result_with({RELAY_META: {"url": f"http://{host}:62480{PAGE}"}}), relays
    )

    assert rewritten.meta is not None
    url = rewritten.meta[RELAY_META]["url"]
    relay_id = relay_id_of(url)
    assert url == f"/api/relay/{relay_id}{PAGE}"
    assert len(relay_id) >= 32
    assert relays.upstream(relay_id) == Upstream(host=host, port=62480)


def test_every_entry_gets_its_own_relay() -> None:
    relays = Relays(now=Now())
    entry = {RELAY_META: {"url": f"http://127.0.0.1:62480{PAGE}"}}

    first = with_relay_url(result_with(entry), relays).meta
    second = with_relay_url(result_with(entry), relays).meta

    assert first is not None and second is not None
    assert relay_id_of(first[RELAY_META]["url"]) != relay_id_of(second[RELAY_META]["url"])


def test_the_rest_of_the_result_is_left_as_it_was() -> None:
    relays = Relays(now=Now())
    original = result_with({RELAY_META: {"url": f"http://127.0.0.1:1{PAGE}"}, "ts": 1})

    rewritten = with_relay_url(original, relays)

    assert rewritten.content == original.content
    assert rewritten.meta is not None
    assert rewritten.meta["ts"] == 1


@pytest.mark.parametrize(
    "entry",
    [
        {"url": "http://example.com/embed.html"},
        {"url": "http://10.0.0.5:6080/embed.html"},
        {"url": "https://127.0.0.1:62480/embed.html"},
        {"url": "ws://127.0.0.1:62480/websockify"},
        {"url": "http://127.0.0.1.example.com/embed.html"},
        {"url": "http://127.0.0.1:notaport/embed.html"},
        {"url": "/api/relay/elsewhere"},
        {"url": 42},
        {"href": "http://127.0.0.1:62480/"},
        "http://127.0.0.1:62480/",
    ],
)
def test_an_entry_that_is_not_http_on_loopback_is_dropped_and_no_relay_made(
    entry: object, caplog: pytest.LogCaptureFixture
) -> None:
    relays = Relays(now=Now())

    with caplog.at_level(logging.WARNING, logger="harness.relay"):
        rewritten = with_relay_url(result_with({RELAY_META: entry, "ts": 1}), relays)

    assert rewritten.meta == {"ts": 1}
    assert relays._relays == {}
    assert "dropped a relay entry" in caplog.text


def test_a_result_without_the_entry_is_unchanged() -> None:
    relays = Relays(now=Now())
    plain = result_with({"ts": 1})

    assert with_relay_url(plain, relays) is plain
    assert with_relay_url(result_with(None), relays).meta is None
    assert relays._relays == {}


def test_a_relay_ends_sixty_minutes_after_it_was_made() -> None:
    now = Now()
    relays = Relays(now=now)
    relay_id = relays.open(Upstream(host="127.0.0.1", port=1))

    now.seconds += RELAY_TTL_SECONDS - 1
    assert relays.upstream(relay_id) is not None

    now.seconds += 1
    assert RELAY_TTL_SECONDS == 60 * 60
    assert relays.upstream(relay_id) is None


def test_an_unknown_relay_reaches_nothing() -> None:
    assert Relays(now=Now()).upstream("nope") is None


def test_ended_relays_are_forgotten_when_the_next_one_opens() -> None:
    now = Now()
    relays = Relays(now=now)
    old = relays.open(Upstream(host="127.0.0.1", port=1))
    now.seconds += RELAY_TTL_SECONDS

    relays.open(Upstream(host="127.0.0.1", port=2))

    assert old not in relays._relays


def test_an_upstream_names_its_page_and_socket_with_the_query_kept() -> None:
    upstream = Upstream(host="127.0.0.1", port=62480)

    assert upstream.http_url("core/rfb.js", "") == "http://127.0.0.1:62480/core/rfb.js"
    assert upstream.ws_url("websockify", "token=t") == "ws://127.0.0.1:62480/websockify?token=t"
