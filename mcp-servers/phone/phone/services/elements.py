"""The phone's screen as text: the elements Android's `uiautomator dump` sees, one line each."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ElementTree

from phone.engine import Engine
from phone.models.command import stdout_of
from phone.models.phone import android

DUMP_PATH = "/data/local/tmp/cell-harness-ui.xml"
DUMP = android(f"uiautomator dump {DUMP_PATH} >/dev/null && cat {DUMP_PATH}")
DUMP_TIMEOUT_SECONDS = 30.0
DOCTYPE = "<!DOCTYPE"
HIERARCHY = "hierarchy"
NODE = "node"
BOUNDS = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")
NOTHING_ON_SCREEN = "Nothing on the phone's screen has words or a description."


class ElementsError(RuntimeError):
    """The screen could not be read as elements. The message says why, in plain words."""


def hierarchy_of(dump: str) -> ElementTree.Element:
    """The dump's root, or a refusal unless it is a plain `hierarchy` document."""
    if DOCTYPE in dump:
        raise ElementsError("The phone's screen dump declares a DOCTYPE, so it was not read")
    try:
        root = ElementTree.fromstring(dump)
    except ElementTree.ParseError as err:
        raise ElementsError(f"The phone's screen dump is not XML: {err}") from err
    if root.tag != HIERARCHY:
        raise ElementsError(f"The phone's screen dump is a {root.tag!r}, not a hierarchy")
    return root


def centre_of(bounds: str) -> tuple[int, int]:
    """The integer midpoint of Android's `[x1,y1][x2,y2]` bounds."""
    found = BOUNDS.fullmatch(bounds)
    if found is None:
        raise ElementsError(f"The phone's screen dump has bounds it cannot read: {bounds!r}")
    x1, y1, x2, y2 = (int(value) for value in found.groups())
    return (x1 + x2) // 2, (y1 + y2) // 2


def element_line(node: ElementTree.Element) -> str | None:
    """One element as a line, or None when it has no words and no description."""
    text = node.get("text", "")
    description = node.get("content-desc", "")
    if not text and not description:
        return None
    parts = [f'text "{text}"'] if text else []
    parts += [f'description "{description}"'] if description else []
    resource_id = node.get("resource-id", "")
    parts += [f"id {resource_id}"] if resource_id else []
    parts += ["clickable"] if node.get("clickable") == "true" else []
    x, y = centre_of(node.get("bounds", ""))
    parts.append(f"center ({x}, {y})")
    return "- " + ", ".join(parts)


def elements_text(dump: str) -> str:
    """Every element with words or a description, one line each, or that there are none."""
    lines = [element_line(node) for node in hierarchy_of(dump).iter(NODE)]
    kept = [line for line in lines if line is not None]
    return "\n".join(kept) if kept else NOTHING_ON_SCREEN


class Elements:
    """The phone's screen, read as its elements."""

    def __init__(self, *, engine: Engine, name: str) -> None:
        self._engine = engine
        self._name = name

    async def listed(self) -> str:
        completed = await self._engine.run(
            self._name, DUMP, stdin=None, timeout_seconds=DUMP_TIMEOUT_SECONDS
        )
        return elements_text(stdout_of(completed, "Reading the screen", error=ElementsError))
