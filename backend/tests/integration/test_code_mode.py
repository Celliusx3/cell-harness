"""Code mode against a real Deno: the whole path, and the codegen it rests on."""

from __future__ import annotations

import json
import shutil
import subprocess
import urllib.parse

import pytest

from harness.llm import ToolCall
from harness.sandbox import DenoRunner
from harness.tools import (
    Ok,
    Tool,
    ToolOutcome,
    ToolService,
    Toolset,
)
from harness.tools.native.code_mode import (
    EXECUTE_TYPESCRIPT,
    GET_FUNCTION_DETAILS,
    LIST_FUNCTIONS,
    code_mode_tools,
)
from harness.tools.native.code_mode._typescript import declarations
from tests.unit.helpers import ORIGIN, no_approvals, no_progress

deno = pytest.mark.skipif(shutil.which("deno") is None, reason="deno is not installed")


def tool(name: str, schema: object, description: str = "A tool.") -> Tool:
    async def run(args, progress):
        return Ok("")

    return Tool(
        name=name,
        description=description,
        input_schema=schema,
        parse=lambda raw: raw,
        execute=run,
    )


def type_check(source: str) -> subprocess.CompletedProcess[str]:
    """Ask Deno to load the source as a module, which parses and type-strips it."""
    url = "data:text/typescript," + urllib.parse.quote(source)
    return subprocess.run(
        ["deno", "run", "--no-prompt", url],
        capture_output=True,
        text=True,
        timeout=60,
    )


@deno
def test_generated_declarations_are_valid_typescript() -> None:
    tools = [
        tool(
            "yt__get_subtitles",
            {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "lang": {"type": ["string", "null"]},
                    "fmt": {"type": "string", "enum": ["srt", "vtt"]},
                    "tags": {"type": "array", "items": {"enum": ["a", "b"]}},
                    "content-type": {"type": "string"},
                },
                "required": ["url"],
            },
            "Fetch subtitles.\nAcross lines, with a */ inside.",
        ),
        tool("jobs__search", {"type": "object", "properties": {}}),
        tool("clock", "a hostile schema, not a dict"),
    ]

    result = type_check(declarations(tools, with_types=True))

    assert result.returncode == 0, result.stderr


@deno
def test_a_script_can_be_written_against_the_declarations() -> None:
    source = declarations(
        [
            tool(
                "yt__get_subtitles",
                {
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
            )
        ],
        with_types=True,
    )
    source += "\nasync function _unused() { await yt__get_subtitles({ url: 'x' }); }\n"

    result = type_check(source)

    assert result.returncode == 0, result.stderr


@deno
async def test_a_script_reaches_a_real_tool_through_a_real_toolset() -> None:

    async def rows(args, progress):
        return Ok("Found 3 rows.", data={"rows": [{"n": 1}, {"n": 2}, {"n": 3}]})

    catalog = Tool(
        name="db__query",
        description="Run a query.",
        input_schema={
            "type": "object",
            "properties": {"sql": {"type": "string"}},
            "required": ["sql"],
        },
        parse=lambda raw: raw,
        execute=rows,
    )
    tool_service = ToolService([catalog], approvals=no_approvals())
    for built in code_mode_tools(
        tool_service=tool_service,
        runner=DenoRunner(deno_path="deno", timeout_seconds=30),
        withheld=frozenset(),
    ):
        tool_service.register(built)
    toolset = Toolset(tool_service, (LIST_FUNCTIONS, GET_FUNCTION_DETAILS, EXECUTE_TYPESCRIPT))

    async def run(name: str, arguments: str) -> ToolOutcome:
        call = ToolCall(id="c1", name=name, arguments=arguments)
        return await toolset.execute(call, progress=no_progress, origin=ORIGIN)

    assert [spec.name for spec in toolset.specs()] == [
        LIST_FUNCTIONS,
        GET_FUNCTION_DETAILS,
        EXECUTE_TYPESCRIPT,
    ]

    listed = await run(LIST_FUNCTIONS, "{}")
    assert isinstance(listed, Ok)
    assert "db__query" in listed.text

    typed = await run(GET_FUNCTION_DETAILS, json.dumps({"names": ["db__query"]}))
    assert isinstance(typed, Ok)
    assert "sql: string" in typed.text

    script = (
        "const r = await db__query({ sql: 'select 1' });\n"
        "console.log('fetched', r.rows.length, 'rows');\n"
        "return r.rows.filter((x) => x.n > 1).map((x) => x.n);"
    )
    ran = await run(EXECUTE_TYPESCRIPT, json.dumps({"code": script, "description": "count rows"}))

    assert isinstance(ran, Ok)
    assert "fetched 3 rows" in ran.text
    assert ran.data == [2, 3]
    assert '"n"' not in ran.text
