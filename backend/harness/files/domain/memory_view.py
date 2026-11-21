"""What a bot is shown of a workspace's memory on every step, capped."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from harness.files.domain.prompts import (
    GROUP_MEMORY,
    GROUP_NO_MEMORY,
    WORKSPACE_MEMORY,
    WORKSPACE_MEMORY_CHARS_CUT,
    WORKSPACE_MEMORY_CUT,
    WORKSPACE_NO_MEMORY,
)

MEMORY_PATH = PurePosixPath("memory/MEMORY.md")
SHOWN_MEMORY_LINES = 200
SHOWN_MEMORY_CHARS = 25_000


@dataclass(frozen=True)
class Wording:
    """How one workspace's memory, or its lack, is named."""

    memory: str
    no_memory: str


OWN_WORDING = Wording(WORKSPACE_MEMORY, WORKSPACE_NO_MEMORY)
GROUP_WORDING = Wording(GROUP_MEMORY, GROUP_NO_MEMORY)


def memory_view(path: str, memory: str | None, wording: Wording) -> str:
    """`memory`, the text at `path`, up to its line and character caps, or that there is none."""
    if memory is None:
        return wording.no_memory.format(path=path)
    lines = memory.splitlines()
    kept = "\n".join(lines[:SHOWN_MEMORY_LINES])
    shown = [wording.memory.format(path=path), *kept[:SHOWN_MEMORY_CHARS].splitlines()]
    if len(kept) > SHOWN_MEMORY_CHARS:
        shown.append(
            WORKSPACE_MEMORY_CHARS_CUT.format(
                path=path, total=len(memory), shown=SHOWN_MEMORY_CHARS
            )
        )
    elif len(lines) > SHOWN_MEMORY_LINES:
        shown.append(
            WORKSPACE_MEMORY_CUT.format(path=path, total=len(lines), shown=SHOWN_MEMORY_LINES)
        )
    return "\n".join(shown)
