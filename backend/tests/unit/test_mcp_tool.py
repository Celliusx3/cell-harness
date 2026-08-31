"""Turning a server's tools into tools the model can call."""

from __future__ import annotations

from mcp.types import AudioContent, CallToolResult, ImageContent, TextContent

from harness.mcp.errors import McpNotConnectedError, McpTimeoutError
from harness.mcp.tool import build_tools, mcp_tool, render_content
from harness.tools.definition import EXECUTION_ERROR, UNKNOWN_TOOL, Failure, Ok
from tests.unit.helpers import no_progress
from tests.unit.mcp_fakes import text_result, tool


async def never_called(name: str, arguments: dict) -> CallToolResult:
    raise AssertionError("should not have been called")


def one(server: str, published, call) -> object:
    return build_tools(server, [published], call)[0]


async def test_the_published_schema_is_relayed_byte_for_byte() -> None:
    """Keys our own Pydantic models could never produce must survive."""
    schema = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "additionalProperties": True,
        "x-vendor-extension": {"deep": [1, 2]},
    }

    built = one("fs", tool("read", schema=schema), never_called)

    assert built.input_schema == schema
    assert built.spec().input_schema == schema


async def test_an_unknown_argument_reaches_the_server_untouched() -> None:
    """`parse` is the identity, so we cannot drop what the server accepts."""
    seen: list[dict] = []

    async def call(name: str, arguments: dict) -> CallToolResult:
        seen.append(arguments)
        return text_result("ok")

    built = one("fs", tool("read"), call)
    await built.invoke('{"path": "/x", "undeclared": 7}', progress=no_progress)

    assert seen == [{"path": "/x", "undeclared": 7}]


async def test_a_tool_that_reports_an_error_becomes_a_failure() -> None:
    """`is_error` is returned, never raised — reading only `content` hides it."""

    async def call(name: str, arguments: dict) -> CallToolResult:
        return text_result("disk is full", is_error=True)

    built = one("fs", tool("write"), call)
    outcome = await built.invoke("{}", progress=no_progress)

    assert outcome == Failure(EXECUTION_ERROR, "disk is full")


async def test_an_error_with_no_message_still_names_the_tool() -> None:
    async def call(name: str, arguments: dict) -> CallToolResult:
        return CallToolResult(content=[], isError=True)

    built = one("fs", tool("write"), call)
    outcome = await built.invoke("{}", progress=no_progress)

    assert isinstance(outcome, Failure)
    assert "fs__write" in outcome.message


async def test_a_disconnected_server_reports_the_tool_as_unknown() -> None:
    """Not EXECUTION_ERROR: the model must learn the tool is gone, not broken."""

    async def call(name: str, arguments: dict) -> CallToolResult:
        raise McpNotConnectedError("stub is not connected")

    built = one("stub", tool("echo"), call)
    outcome = await built.invoke("{}", progress=no_progress)

    assert isinstance(outcome, Failure)
    assert outcome.code == UNKNOWN_TOOL


async def test_a_timeout_is_an_execution_error_carrying_the_reason() -> None:
    async def call(name: str, arguments: dict) -> CallToolResult:
        raise McpTimeoutError("stub did not answer 'echo' within 60s")

    built = one("stub", tool("echo"), call)
    outcome = await built.invoke("{}", progress=no_progress)

    assert outcome == Failure(EXECUTION_ERROR, "stub did not answer 'echo' within 60s")


async def test_structured_content_is_used_when_there_are_no_blocks() -> None:
    async def call(name: str, arguments: dict) -> CallToolResult:
        return CallToolResult(content=[], structuredContent={"rows": 3})

    built = one("db", tool("count"), call)
    outcome = await built.invoke("{}", progress=no_progress)

    assert outcome == Ok('{"rows": 3}')


def test_text_blocks_are_joined_in_order() -> None:
    blocks = [TextContent(type="text", text="one"), TextContent(type="text", text="two")]
    assert render_content(blocks) == "one\ntwo"


def test_an_image_is_described_and_its_payload_never_appears() -> None:
    """base64 here would enter the log and then every later model request."""
    payload = "QUJDREVGR0g="
    rendered = render_content([ImageContent(type="image", data=payload, mimeType="image/png")])

    assert payload not in rendered
    assert "image/png" in rendered
    assert str(len(payload)) in rendered


def test_an_unrenderable_block_is_named_rather_than_dropped() -> None:
    rendered = render_content([AudioContent(type="audio", data="AAA=", mimeType="audio/wav")])
    assert rendered == "[AudioContent]"


def test_a_name_no_provider_would_accept_is_dropped_not_relayed() -> None:
    """One bad name fails the whole request, killing every turn — not just this tool."""
    built = build_tools("srv", [tool("a" * 70), tool("fine"), tool("has/slash")], never_called)

    assert [t.name for t in built] == ["srv__fine"]


def test_a_server_publishing_no_schema_still_gets_a_usable_one() -> None:
    built = mcp_tool(server="srv", tool=tool("bare", schema={}), call=never_called)
    assert built.input_schema == {"type": "object", "properties": {}}
