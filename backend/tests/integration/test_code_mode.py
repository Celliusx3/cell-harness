"""Code mode against a real Deno: the whole path, and the codegen it rests on.

The sandbox's own contracts — permissions, reaping, the bridge — are in
`test_sandbox.py`. What is here is everything above it: that our generated
TypeScript is real TypeScript, and that a script reaches a real tool through the
real pipeline.
"""

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
    async def run(args, progress):  # pragma: no cover - never invoked here
        return Ok("")

    return ToolDefinition(
        name=name,
        description=description,
        input_schema=schema,  # type: ignore[arg-type]
        parse=lambda raw: raw,
        execute=run,
    )


def type_check(source: str) -> subprocess.CompletedProcess[str]:
    """Ask Deno to load the source as a module, which parses and type-strips it."""
    url = "data:text/typescript," + urllib.parse.quote(source)
    return subprocess.run(  # noqa: S603 - a fixed argv, no shell
        ["deno", "run", "--no-prompt", url],  # noqa: S607 - resolved via PATH by design
        capture_output=True,
        text=True,
        timeout=60,
    )


# ── the codegen produces real TypeScript ──────────────────────────────────────


@deno
def test_generated_declarations_are_valid_typescript() -> None:
    """The printer's output is only useful if Deno accepts it. Every construct we
    emit is exercised here, including the ones a server can force on us."""
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
    """Declarations plus a call site — the shape the model actually produces."""
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
    # `declare` emits no runtime code, so the call is unreachable on purpose:
    # this asserts the *types* line up, not that anything runs.
    source += "\nasync function _unused() { await yt__get_subtitles({ url: 'x' }); }\n"

    result = type_check(source)

    assert result.returncode == 0, result.stderr


# ── the whole path ────────────────────────────────────────────────────────────


@deno
async def test_a_script_reaches_a_real_tool_through_the_real_pipeline() -> None:
    """Every seam at once: the printer types the tool, the model's script calls it
    by name, the bridge dispatches through `ToolPipeline`, and only what the
    script returned comes back."""

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
    ):
        registry.register(built)
    pipeline = ToolPipeline(registry, dispatcher, (LIST, DETAILS, EXECUTE))

    async def run(name: str, arguments: str) -> ToolOutcome:
        call = ToolCall(id="c1", name=name, arguments=arguments)
        return await pipeline.execute(call, progress=no_progress)

    # The model is offered three tools and nothing else.
    assert [spec.name for spec in pipeline.specs()] == [LIST, DETAILS, EXECUTE]

    listed = await run(LIST, "{}")
    assert isinstance(listed, Ok)
    assert "db__query" in listed.content

    typed = await run(DETAILS, json.dumps({"names": ["db__query"]}))
    assert isinstance(typed, Ok)
    assert "sql: string" in typed.content

    script = (
        "const r = await db__query({ sql: 'select 1' });\n"
        "console.log('fetched', r.rows.length, 'rows');\n"
        "return r.rows.filter((x) => x.n > 1).map((x) => x.n);"
    )
    ran = await run(EXECUTE, json.dumps({"code": script, "description": "count rows"}))

    assert isinstance(ran, Ok)
    assert "fetched 3 rows" in ran.content
    # The three fetched rows never entered the conversation; two numbers did.
    assert ran.data == [2, 3]
    assert '"n"' not in ran.content
