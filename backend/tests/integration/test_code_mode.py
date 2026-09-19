"""Code mode against a real Deno: the whole path, and the codegen it rests on."""

from __future__ import annotations

import json
import shutil
import subprocess
import urllib.parse

import pytest

from harness.llm.messages import ToolCall
from harness.sandbox import DenoRunner
from harness.tools.definition import Ok, ToolDefinition, ToolOutcome
from harness.tools.dispatcher import ToolDispatcher
from harness.tools.native.code import DETAILS, EXECUTE, LIST, code_mode_tools
from harness.tools.native.code.typescript import declarations
from harness.tools.pipeline import ToolPipeline
from harness.tools.registry import ToolRegistry
from tests.unit.helpers import no_progress

deno = pytest.mark.skipif(shutil.which("deno") is None, reason="deno is not installed")


def tool(name: str, schema: object, description: str = "A tool.") -> ToolDefinition:
    async def run(args, progress):
        return Ok("")

    return ToolDefinition(
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

    result = type_check(declarations(tools, types=True))

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
        types=True,
    )
    source += "\nasync function _unused() { await yt__get_subtitles({ url: 'x' }); }\n"

    result = type_check(source)

    assert result.returncode == 0, result.stderr


@deno
async def test_a_script_reaches_a_real_tool_through_the_real_pipeline() -> None:

    async def rows(args, progress):
        return Ok("Found 3 rows.", data={"rows": [{"n": 1}, {"n": 2}, {"n": 3}]})

    catalog = ToolDefinition(
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
    registry = ToolRegistry([catalog])
    dispatcher = ToolDispatcher(registry)
    for built in code_mode_tools(
        registry=registry,
        dispatcher=dispatcher,
        runtime=DenoRunner(deno_path="deno", timeout_seconds=30),
        withheld=frozenset(),
    ):
        registry.register(built)
    pipeline = ToolPipeline(registry, dispatcher, (LIST, DETAILS, EXECUTE))

    async def run(name: str, arguments: str) -> ToolOutcome:
        call = ToolCall(id="c1", name=name, arguments=arguments)
        return await pipeline.execute(call, progress=no_progress)

    assert [spec.name for spec in pipeline.specs()] == [LIST, DETAILS, EXECUTE]

    listed = await run(LIST, "{}")
    assert isinstance(listed, Ok)
    assert "db__query" in listed.text

    typed = await run(DETAILS, json.dumps({"names": ["db__query"]}))
    assert isinstance(typed, Ok)
    assert "sql: string" in typed.text

    script = (
        "const r = await db__query({ sql: 'select 1' });\n"
        "console.log('fetched', r.rows.length, 'rows');\n"
        "return r.rows.filter((x) => x.n > 1).map((x) => x.n);"
    )
    ran = await run(EXECUTE, json.dumps({"code": script, "description": "count rows"}))

    assert isinstance(ran, Ok)
    assert "fetched 3 rows" in ran.text
    assert ran.data == [2, 3]
    assert '"n"' not in ran.text
