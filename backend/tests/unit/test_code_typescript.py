"""The tool catalog as TypeScript."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from harness.tools.definition import Ok, ToolDefinition
from harness.tools.native.code.typescript import MAX_DEPTH, declarations


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


def rendered(schema: object) -> str:
    """The args clause for one tool, which is what most of these assert on."""
    return declarations([tool("srv__t", schema)], types=True).splitlines()[-1]


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


def test_refs_from_a_pydantic_model_resolve() -> None:

    class Inner(BaseModel):
        depth: int

    class Args(BaseModel):
        nested: Inner

    built = ToolDefinition.from_model(
        name="clock", description="d", args_model=Args, execute=lambda a, p: None
    )

    assert "nested: { depth: number }" in declarations([built], types=True)


def test_a_ref_cycle_terminates() -> None:
    schema = {
        "type": "object",
        "properties": {"child": {"$ref": "#/$defs/Node"}},
        "$defs": {"Node": {"type": "object", "properties": {"child": {"$ref": "#/$defs/Node"}}}},
    }

    assert "unknown" in rendered(schema)


def test_deep_nesting_is_bounded() -> None:
    schema: dict = {"type": "string"}
    for _ in range(MAX_DEPTH + 5):
        schema = {"type": "object", "properties": {"n": schema}}

    assert "unknown" in rendered(schema)


def test_a_property_name_that_is_not_an_identifier_is_quoted() -> None:
    line = rendered({"type": "object", "properties": {"content-type": {"type": "string"}}})

    assert '"content-type"?: string' in line


@pytest.mark.parametrize(
    "schema",
    [None, "not a schema", 42, [], {"type": "wat"}, {"properties": "not a dict"}],
)
def test_a_hostile_schema_degrades_instead_of_raising(schema: object) -> None:
    assert "declare function srv__t(" in rendered(schema)


def test_signatures_elide_argument_types() -> None:
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
    line = declarations(
        [tool("srv__t", {}, "Two\nlines  and a */ inside.")], types=False
    ).splitlines()[1]

    assert line == "/** Two lines and a *\\/ inside. */"


def test_rendering_is_deterministic() -> None:
    tools = [tool("b__x", {"type": "object"}), tool("a__y", {"type": "object"})]

    assert declarations(tools, types=True) == declarations(list(reversed(tools)), types=True)
