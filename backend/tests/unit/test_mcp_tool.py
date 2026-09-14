"""Turning a server's tools into tools the model can call."""

from __future__ import annotations

import re

from mcp.types import AudioContent, CallToolResult, ImageContent, TextContent

from harness.mcp.errors import McpNotConnectedError, McpTimeoutError
from harness.mcp.tool import build_tools, mcp_tool, render_content, ui_resource_uri
from harness.tools.definition import EXECUTION_ERROR, UNKNOWN_TOOL, Failure, Ok, ToolUi
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
    """With nothing to render, the structured value stands in as the text too."""

    async def call(name: str, arguments: dict) -> CallToolResult:
        return CallToolResult(content=[], structuredContent={"rows": 3})

    built = one("db", tool("count"), call)
    outcome = await built.invoke("{}", progress=no_progress)

    assert outcome == Ok('{"rows": 3}', data={"rows": 3})


async def test_structured_content_survives_alongside_text() -> None:
    """A server that sends a summary *and* the rows means both. Keeping only the
    summary destroyed the rows, and nothing downstream could ask for them back."""

    async def call(name: str, arguments: dict) -> CallToolResult:
        return CallToolResult(
            content=[TextContent(type="text", text="Found 3 jobs.")],
            structuredContent={"jobs": [{"title": "Senior Python Engineer"}]},
        )

    built = one("jobs", tool("search"), call)
    outcome = await built.invoke("{}", progress=no_progress)

    assert isinstance(outcome, Ok)
    assert outcome.text == "Found 3 jobs."
    assert outcome.data == {"jobs": [{"title": "Senior Python Engineer"}]}


async def test_a_tool_with_no_structured_content_has_none() -> None:
    async def call(name: str, arguments: dict) -> CallToolResult:
        return CallToolResult(content=[TextContent(type="text", text="hi")])

    built = one("stub", tool("echo"), call)

    assert await built.invoke("{}", progress=no_progress) == Ok("hi")


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


async def test_a_hyphenated_name_is_mapped_for_the_model_and_kept_for_the_server() -> None:
    """Providers accept a hyphen; `tools/native/code/typescript.py` emits
    `declare function {name}(...)` **unquoted**, so a hyphenated name is
    unparseable TypeScript. Every public MCP App is named `get-time`, so the
    hyphen is mapped rather than the tool dropped — and the server is still
    called by the name it published."""
    asked: list[str] = []

    async def call(name: str, arguments: dict) -> CallToolResult:
        asked.append(name)
        return text_result("ok")

    built = one("srv", tool("get-video"), call)
    await built.invoke("{}", progress=no_progress)

    assert built.name == "srv__get_video"
    assert asked == ["get-video"]
    # Note a leading digit in the *tool* name is fine — `srv__9lives` still
    # starts with the server id. It is the *id* that must start with a letter,
    # which `_SERVER_ID` now enforces (see test_mcp_settings.py).
    assert [t.name for t in build_tools("srv", [tool("9lives")], never_called)] == ["srv__9lives"]


def test_two_tools_that_map_to_one_name_keep_the_first() -> None:
    """Two tools under one name would make the dispatcher's choice silent."""
    built = build_tools("srv", [tool("get-video"), tool("get_video")], never_called)

    assert [t.name for t in built] == ["srv__get_video"]


def test_the_app_binding_is_read_from_the_tool_meta() -> None:
    assert ui_resource_uri(tool("x", meta={"ui": {"resourceUri": "ui://x/app.html"}})) == (
        "ui://x/app.html"
    )
    # `poll-system-stats`' shape: `ui` metadata with no resource at all.
    assert ui_resource_uri(tool("x", meta={"ui": {"visibility": ["app"]}})) is None
    assert ui_resource_uri(tool("x", meta={"ui": {"resourceUri": "https://x"}})) is None
    assert ui_resource_uri(tool("x")) is None


async def test_a_bound_tool_returns_its_app_with_the_structured_content() -> None:
    async def call(name: str, arguments: dict) -> CallToolResult:
        return CallToolResult(
            content=[TextContent(type="text", text="3 rows")], structuredContent={"rows": 3}
        )

    built = one("db", tool("count", meta={"ui": {"resourceUri": "ui://db/app.html"}}), call)
    outcome = await built.invoke("{}", progress=no_progress)

    assert outcome == Ok(
        "3 rows",
        data={"rows": 3},
        ui=ToolUi(server="db", resource_uri="ui://db/app.html", data={"rows": 3}),
    )


async def test_a_bound_tool_that_fails_has_no_app() -> None:
    async def call(name: str, arguments: dict) -> CallToolResult:
        return text_result("nope", is_error=True)

    built = one("db", tool("count", meta={"ui": {"resourceUri": "ui://db/app.html"}}), call)

    assert await built.invoke("{}", progress=no_progress) == Failure(EXECUTION_ERROR, "nope")


def test_every_relayed_name_is_a_usable_typescript_identifier() -> None:
    """The property the two regexes exist to guarantee, asserted directly rather
    than inferred from them — so a future widening of either is caught here."""
    published = [tool("fine"), tool("also_fine"), tool("get-video"), tool("has/slash"), tool("_ok")]

    for built in build_tools("srv", published, never_called):
        assert re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", built.name), built.name


def test_a_server_publishing_no_schema_still_gets_a_usable_one() -> None:
    built = mcp_tool(server="srv", tool=tool("bare", schema={}), call=never_called)
    assert built.input_schema == {"type": "object", "properties": {}}
