"""The tool catalog, as TypeScript the model can write against."""

from __future__ import annotations

import keyword
import logging
from collections.abc import Sequence
from typing import Any

from harness.tools.definition import NAMESPACE, ToolDefinition

logger = logging.getLogger("harness.tools.code")

_PRIMITIVES = {
    "string": "string",
    "integer": "number",
    "number": "number",
    "boolean": "boolean",
    "null": "null",
}

MAX_DEPTH = 8

RETURN_TYPE = "Promise<unknown>"


def declarations(tools: Sequence[ToolDefinition], *, types: bool) -> str:
    """Every tool as a `declare function`, grouped by the server that owns it."""
    groups: dict[str, list[str]] = {}
    for tool in sorted(tools, key=lambda t: t.name):
        server, _, _ = tool.name.partition(NAMESPACE)
        owner = server if NAMESPACE in tool.name else ""
        groups.setdefault(owner, []).append(_declare(tool, types=types))

    blocks: list[str] = []
    for owner, lines in groups.items():
        header = f"// {owner}" if owner else "// built in"
        blocks.append("\n".join([header, *lines]))
    return "\n\n".join(blocks)


def _declare(tool: ToolDefinition, *, types: bool) -> str:
    doc = f"/** {_one_line(tool.description)} */\n" if tool.description else ""
    args = _args_type(tool.input_schema) if types else "args"
    return f"{doc}declare function {tool.name}({args}): {RETURN_TYPE};"


def _one_line(text: str) -> str:
    """One comment line."""
    return " ".join(text.split()).replace("*/", "*\\/")


def _args_type(schema: object) -> str:
    """The `args` parameter, fully typed. Total: any failure yields `args: unknown`."""
    try:
        if not isinstance(schema, dict):
            return "args: unknown"
        defs = _definitions(schema)
        rendered = _render(schema, defs, depth=0, seen=frozenset())
        return "args?: Record<string, never>" if rendered == "{}" else f"args: {rendered}"
    except Exception:
        logger.warning("could not render a tool schema; falling back to unknown", exc_info=True)
        return "args: unknown"


def _definitions(schema: dict) -> dict[str, Any]:
    """`$defs`, plus `definitions` for schemas on an older draft."""
    found: dict[str, Any] = {}
    for key in ("$defs", "definitions"):
        block = schema.get(key)
        if isinstance(block, dict):
            found.update(block)
    return found


def _render(schema: object, defs: dict[str, Any], *, depth: int, seen: frozenset[str]) -> str:
    if depth > MAX_DEPTH or not isinstance(schema, dict):
        return "unknown"

    ref = schema.get("$ref")
    if isinstance(ref, str):
        name = ref.rsplit("/", 1)[-1]
        if name in seen or name not in defs:
            return "unknown"
        return _render(defs[name], defs, depth=depth + 1, seen=seen | {name})

    if "const" in schema:
        return _literal(schema["const"])

    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return " | ".join(dict.fromkeys(_literal(v) for v in enum))

    for key in ("anyOf", "oneOf"):
        branches = schema.get(key)
        if isinstance(branches, list) and branches:
            rendered = dict.fromkeys(_render(b, defs, depth=depth + 1, seen=seen) for b in branches)
            return " | ".join(rendered)

    kind = schema.get("type")
    if isinstance(kind, list):
        return " | ".join(dict.fromkeys(_PRIMITIVES.get(k, "unknown") for k in kind))
    if kind == "array":
        item = _render(schema.get("items"), defs, depth=depth + 1, seen=seen)
        # Parenthesised so `("a" | "b")[]` does not read as `"a" | ("b"[])`.
        return f"({item})[]" if "|" in item else f"{item}[]"
    if kind == "object" or "properties" in schema:
        return _object(schema, defs, depth=depth, seen=seen)
    if isinstance(kind, str) and kind in _PRIMITIVES:
        return _PRIMITIVES[kind]
    return "unknown"


def _object(schema: dict, defs: dict[str, Any], *, depth: int, seen: frozenset[str]) -> str:
    props = schema.get("properties")
    if not isinstance(props, dict) or not props:
        closed = schema.get("additionalProperties") is False
        return "{}" if closed else "Record<string, unknown>"

    required = schema.get("required")
    required = set(required) if isinstance(required, list) else set()
    fields: list[str] = []
    for name, prop in props.items():
        rendered = _render(prop, defs, depth=depth + 1, seen=seen)
        fields.append(f"{_key(name)}{'' if name in required else '?'}: {rendered}")
    return "{ " + "; ".join(fields) + " }"


def _key(name: str) -> str:
    """A property key, quoted unless it is a bare identifier."""
    ok = name.isidentifier() and not keyword.iskeyword(name) and name.isascii()
    return name if ok else _literal(name)


def _literal(value: object) -> str:
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if value is None:
        return "null"
    return "unknown"
