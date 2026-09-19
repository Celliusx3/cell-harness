"""A tool result bound to an MCP App reaches a chat as a link to its page."""

from __future__ import annotations

from harness.channels.replies import app_url
from harness.tools.context import ToolContext
from harness.tools.definition import Ok, ToolDefinition, ToolOutcome, ToolUi
from tests.unit.fakes import (
    EchoArgs,
    SteppedClient,
    calls_tool,
    completed,
    echo_tool,
)
from tests.unit.gateway_helpers import CHAT, build, msg, settle
from tests.unit.helpers import no_skills


def app_tool() -> ToolDefinition[EchoArgs]:
    """A tool whose result is bound to an MCP App."""

    async def execute(args: EchoArgs, context: ToolContext) -> ToolOutcome:
        return Ok(args.value, ui=ToolUi(server="srv", resource_uri="ui://srv/app.html"))

    return ToolDefinition.from_model(
        name="srv__show", description="Show.", args_model=EchoArgs, execute=execute
    )


async def test_a_result_with_an_app_is_delivered_as_a_link_before_the_reply(tmp_path) -> None:
    bot, gateway, runs, _, _ = build(
        tmp_path,
        SteppedClient(calls_tool("srv__show", '{"value": "42"}'), completed("there it is")),
        app_tool(),
        skills=no_skills(),
    )

    await gateway.receive(msg("show me", 1))
    await settle(runs, gateway)

    ((chat_id, text, markup),) = bot.linked
    assert (chat_id, text) == (CHAT, "srv__show")
    assert markup.inline_keyboard[0][0].url == app_url("http://t", "c0", "c1")
    assert bot.sent == [(CHAT, "there it is")]


async def test_a_link_the_platform_refuses_does_not_cost_the_reply(tmp_path) -> None:
    bot, gateway, runs, chats, _ = build(
        tmp_path,
        SteppedClient(calls_tool("srv__show", '{"value": "42"}'), completed("there it is")),
        app_tool(),
        skills=no_skills(),
    )
    bot.refuse_links = RuntimeError("Bad Request: inline keyboard button URL is invalid")

    await gateway.receive(msg("show me", 1))
    await settle(runs, gateway)

    assert bot.linked == []
    assert bot.sent == [(CHAT, "there it is")]
    state = await chats.load("telegram", CHAT)
    assert state is not None and state.delivered_through > 0


async def test_no_public_url_means_no_link(tmp_path) -> None:
    bot, gateway, runs, _, _ = build(
        tmp_path,
        SteppedClient(calls_tool("srv__show", '{"value": "42"}'), completed("there it is")),
        app_tool(),
        public_url="",
        skills=no_skills(),
    )

    await gateway.receive(msg("show me", 1))
    await settle(runs, gateway)

    assert bot.linked == []
    assert bot.sent == [(CHAT, "there it is")]


async def test_a_result_without_an_app_sends_no_link(tmp_path) -> None:
    bot, gateway, runs, _, _ = build(
        tmp_path,
        SteppedClient(calls_tool("echo", '{"value": "42"}'), completed("it is 42")),
        echo_tool(),
        skills=no_skills(),
    )

    await gateway.receive(msg("what is it?", 1))
    await settle(runs, gateway)

    assert bot.linked == []


def test_the_app_page_url_escapes_its_ids() -> None:
    assert app_url("http://t", "c/1", "call:2") == "http://t/apps/c%2F1/call%3A2"
