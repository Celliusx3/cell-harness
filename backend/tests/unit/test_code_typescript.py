"""The tool catalog as TypeScript.

The load-bearing property is that this **never raises**: it runs during prompt
assembly, and its input is third-party JSON Schema relayed verbatim from MCP
servers. Half these tests are about degrading rather than failing.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from harness.tools.definition import Ok, ToolDefinition
from harness.tools.native.code.typescript import MAX_DEPTH, declarations


def tool(name: str, schema: object, description: str = "A tool.") -> ToolDefinition:
    async def run(args, progress):  # pragma: no cover - never invoked here
        return Ok("")

    return ToolDefinition(
        name=name,
        description=description,
        input_schema=schema,  # type: ignore[arg-type]  - deliberately hostile in some tests
        parse=lambda raw: raw,
        execute=run,
    )


def rendered(schema: object) -> str:
    """The args clause for one tool, which is what most of these assert on."""
    return declarations([tool("srv__t", schema)], types=True).splitlines()[-1]


# ── the four conversion rules ─────────────────────────────────────────────────


def test_primitives_and_the_optional_marker() -> None:
    line = rendered(
        {
            "type": "object",
            "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
            "required": ["a"],
        }
    )

    assert "args: { a: string; b?: number }" in line


def test_an_enum_becomes_a_union_of_literals() -> None:
    assert '"srt" | "vtt"' in rendered(
        {"type": "object", "properties": {"fmt": {"type": "string", "enum": ["srt", "vtt"]}}}
    )


def test_an_array_of_a_union_is_parenthesised() -> None:
    """`"a" | "b"[]` would parse as `"a" | ("b"[])` — the wrong type."""
    line = rendered(
        {
            "type": "object",
            "properties": {"x": {"type": "array", "items": {"enum": ["a", "b"]}}},
        }
    )

    assert '("a" | "b")[]' in line


def test_a_nullable_type_list_becomes_a_union() -> None:
    assert "string | null" in rendered(
        {"type": "object", "properties": {"a": {"type": ["string", "null"]}}}
    )


# ── schemas we do not control ─────────────────────────────────────────────────


def test_refs_from_a_pydantic_model_resolve() -> None:
    """`model_json_schema()` emits `$defs`/`$ref` for any nested model, so a
    printer that ignored them would render every native tool as `unknown`."""

    class Inner(BaseModel):
        depth: int

    class Args(BaseModel):
        nested: Inner

    built = ToolDefinition.from_model(
        name="clock", description="d", args_model=Args, execute=lambda a, p: None
    )

    assert "nested: { depth: number }" in declarations([built], types=True)


def test_a_ref_cycle_terminates() -> None:
    """A self-referential schema is legal and common. Only the second visit is a
    loop, so the guard is by name rather than by depth."""
    schema = {
        "type": "object",
        "properties": {"child": {"$ref": "#/$defs/Node"}},
        "$defs": {"Node": {"type": "object", "properties": {"child": {"$ref": "#/$defs/Node"}}}},
    }

    assert "unknown" in rendered(schema)


def test_deep_nesting_is_bounded() -> None:
    """Not a correctness bound — a bound on how much prompt one tool can eat."""
    schema: dict = {"type": "string"}
    for _ in range(MAX_DEPTH + 5):
        schema = {"type": "object", "properties": {"n": schema}}

    assert "unknown" in rendered(schema)


def test_a_property_name_that_is_not_an_identifier_is_quoted() -> None:
    """Server-published names are not ours to control; `content-type` is legal
    JSON and illegal TypeScript."""
    line = rendered({"type": "object", "properties": {"content-type": {"type": "string"}}})

    assert '"content-type"?: string' in line


@pytest.mark.parametrize(
    "schema",
    [None, "not a schema", 42, [], {"type": "wat"}, {"properties": "not a dict"}],
)
def test_a_hostile_schema_degrades_instead_of_raising(schema: object) -> None:
    """The whole point. An exception here kills the turn for every tool, not just
    the one with the bad schema."""
    assert "declare function srv__t(" in rendered(schema)


# ── the catalog view ──────────────────────────────────────────────────────────


def test_signatures_elide_argument_types() -> None:
    """What makes two-stage disclosure cheaper than handing over every schema."""
    big = {"type": "object", "properties": {f"f{i}": {"type": "string"} for i in range(20)}}

    catalog = declarations([tool("srv__t", big)], types=False)

    assert "declare function srv__t(args): Promise<unknown>;" in catalog
    assert "f0" not in catalog


def test_tools_are_grouped_by_server_and_sorted() -> None:
    out = declarations(
        [tool("yt__b", {}), tool("jobs__a", {}), tool("yt__a", {}), tool("clock", {})],
        types=False,
    )

    assert out.index("// built in") < out.index("// jobs") < out.index("// yt")
    assert out.index("yt__a") < out.index("yt__b")


def test_a_description_becomes_one_safe_comment_line() -> None:
    """A newline or a `*/` in a server's description would end the comment early
    and make the rest of the block parse as code."""
    line = declarations(
        [tool("srv__t", {}, "Two\nlines  and a */ inside.")], types=False
    ).splitlines()[1]

    assert line == "/** Two lines and a *\\/ inside. */"


def test_rendering_is_deterministic() -> None:
    """Byte-identical for an unchanged tool set, so the prompt does not churn."""
    tools = [tool("b__x", {"type": "object"}), tool("a__y", {"type": "object"})]

    assert declarations(tools, types=True) == declarations(list(reversed(tools)), types=True)
