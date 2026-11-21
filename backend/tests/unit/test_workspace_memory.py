"""What a bot is shown of its memory on every step: `memory/MEMORY.md` in each of its workspaces."""

from __future__ import annotations

from pathlib import Path

from harness.files import WorkspaceTextRepository, WorkspaceTextService
from harness.files.domain.memory_view import (
    MEMORY_PATH,
    OWN_WORDING,
    SHOWN_MEMORY_CHARS,
    SHOWN_MEMORY_LINES,
    memory_view,
)
from harness.runtime.hooks.native.workspace_memory import WorkspaceMemoryHook
from harness.session.domain.models import WorkspaceEvent


def hook() -> WorkspaceMemoryHook:
    return WorkspaceMemoryHook(WorkspaceTextService(WorkspaceTextRepository()))


def folder(tmp_path: Path, name: str, memory: bytes | None = None) -> Path:
    """A workspace named `name`, holding `memory` as its `MEMORY_PATH` when given."""
    made = (tmp_path / name).resolve()
    made.mkdir(parents=True, exist_ok=True)
    if memory is not None:
        (made / MEMORY_PATH).parent.mkdir()
        (made / MEMORY_PATH).write_bytes(memory)
    return made


def named(workspace: Path, own: Path | None = None) -> WorkspaceEvent:
    own_workspace = None if own is None else str(own)
    return WorkspaceEvent(bot_id="b", workspace=str(workspace), own_workspace=own_workspace)


def test_the_memory_is_shown_under_its_path() -> None:
    text = memory_view("/w/memory/MEMORY.md", "- Client accepts PDF only\n", OWN_WORDING)

    assert text == "Your memory, /w/memory/MEMORY.md:\n- Client accepts PDF only"


def test_no_memory_says_so() -> None:
    assert memory_view("/w/memory/MEMORY.md", None, OWN_WORDING) == (
        "You have no memory yet: /w/memory/MEMORY.md does not exist."
    )


def test_a_long_memory_is_cut_at_its_cap_with_a_note() -> None:
    lines = [f"line {n}" for n in range(1, 301)]

    text = memory_view("/w/memory/MEMORY.md", "\n".join(lines), OWN_WORDING)

    assert SHOWN_MEMORY_LINES == 200
    assert "line 200\n" in text
    assert "line 201" not in text
    assert text.endswith(
        "/w/memory/MEMORY.md has 300 lines and only the first 200 are shown. Keep it short: "
        "move details into other files and leave one line pointing to each."
    )


async def test_the_hook_shows_the_memory_and_no_other_file(tmp_path: Path) -> None:
    workspace = folder(tmp_path, "chat", b"- Client accepts PDF only\n")
    (workspace / "plan.md").write_text("secret plan body\n")

    text = await hook().start_of_step(named(workspace))

    assert text == f"Your memory, {workspace / MEMORY_PATH}:\n- Client accepts PDF only"


async def test_in_a_group_the_bot_sees_its_own_memory_then_the_group_s(tmp_path: Path) -> None:
    group = folder(tmp_path, "group", b"- Launch is in May\n")
    own = folder(tmp_path, "own")

    text = await hook().start_of_step(named(group, own))

    assert text == (
        f"You have no memory yet: {own / MEMORY_PATH} does not exist.\n\n"
        f"This group's memory, {group / MEMORY_PATH}:\n- Launch is in May"
    )


async def test_a_memory_that_is_not_text_is_left_out(tmp_path: Path) -> None:
    group = folder(tmp_path, "group", b"\xff\xfe\x00bad")
    own = folder(tmp_path, "own", b"- mine\n")

    text = await hook().start_of_step(named(group, own))

    assert text == f"Your memory, {own / MEMORY_PATH}:\n- mine"


async def test_a_turn_told_no_workspace_is_shown_nothing() -> None:
    assert await hook().start_of_step(None) is None


def test_a_memory_of_few_long_lines_is_cut_at_its_character_cap() -> None:
    memory = "\n".join("x" * 1000 for _ in range(100))

    text = memory_view("/w/memory/MEMORY.md", memory, OWN_WORDING)

    assert len(text) < SHOWN_MEMORY_CHARS + 500
    assert text.endswith(
        f"/w/memory/MEMORY.md has {len(memory)} characters and only the first "
        f"{SHOWN_MEMORY_CHARS} are shown. Keep it short: "
        "move details into other files and leave one line pointing to each."
    )
