"""A bot edits a workspace file only as it last read it, as Claude Code's edit tool does."""

from __future__ import annotations

from pathlib import Path

from harness.tools import Failure, Ok
from harness.tools.native.workspace import (
    WORKSPACE_EDIT,
    WORKSPACE_READ,
    WORKSPACE_WRITE,
    _descriptions,
)
from tests.unit.test_workspace_tools import call, chat_folder, origin_in, text_of, tools_in


def written(tmp_path: Path) -> str:
    return str(chat_folder(tmp_path) / "a.md")


async def test_an_edit_of_a_file_this_history_never_read_is_refused(tmp_path: Path) -> None:
    tools, path = tools_in(), written(tmp_path)
    await call(tools, WORKSPACE_WRITE, origin_in(tmp_path), path=path, text="one\n")
    worker = origin_in(tmp_path, history_id="worker-1@0")

    edit = await call(tools, WORKSPACE_EDIT, worker, path=path, find="one", replace="1")

    assert isinstance(edit, Failure)
    assert text_of(edit) == (
        f"error: {path} has not been read yet. Read it with workspace_read before editing it."
    )
    assert Path(path).read_text() == "one\n"


async def test_an_edit_after_a_read_lands(tmp_path: Path) -> None:
    tools, path = tools_in(), written(tmp_path)
    await call(tools, WORKSPACE_WRITE, origin_in(tmp_path), path=path, text="one\n")
    worker = origin_in(tmp_path, history_id="worker-1@0")

    await call(tools, WORKSPACE_READ, worker, path=path, start_line=1, end_line=1)
    edit = await call(tools, WORKSPACE_EDIT, worker, path=path, find="one", replace="1")

    assert isinstance(edit, Ok)
    assert Path(path).read_text() == "1\n"


async def test_an_edit_of_a_file_changed_since_the_read_is_refused_until_read_again(
    tmp_path: Path,
) -> None:
    tools, path, bot = tools_in(), written(tmp_path), origin_in(tmp_path)
    worker = origin_in(tmp_path, history_id="worker-1@0")
    await call(tools, WORKSPACE_WRITE, bot, path=path, text="one\ntwo\n")
    await call(tools, WORKSPACE_READ, worker, path=path)
    await call(tools, WORKSPACE_EDIT, bot, path=path, find="two", replace="2")

    stale = await call(tools, WORKSPACE_EDIT, worker, path=path, find="one", replace="1")
    await call(tools, WORKSPACE_READ, worker, path=path)
    fresh = await call(tools, WORKSPACE_EDIT, worker, path=path, find="one", replace="1")

    assert text_of(stale) == (
        f"error: {path} changed since you last read it. Read it again with workspace_read "
        "before editing it."
    )
    assert isinstance(fresh, Ok)
    assert Path(path).read_text() == "1\n2\n"


async def test_a_file_changed_on_disk_since_the_read_is_refused(tmp_path: Path) -> None:
    tools, path, bot = tools_in(), written(tmp_path), origin_in(tmp_path)
    await call(tools, WORKSPACE_WRITE, bot, path=path, text="one\n")
    Path(path).write_text("one\nadded by a program\n")

    edit = await call(tools, WORKSPACE_EDIT, bot, path=path, find="one", replace="1")

    assert isinstance(edit, Failure)
    assert Path(path).read_text() == "one\nadded by a program\n"


async def test_the_same_text_written_back_since_the_read_is_not_a_change(tmp_path: Path) -> None:
    tools, path, bot = tools_in(), written(tmp_path), origin_in(tmp_path)
    await call(tools, WORKSPACE_WRITE, bot, path=path, text="one\n")
    Path(path).write_text("one\n")
    other_spelling = str(chat_folder(tmp_path) / "." / "a.md")

    edit = await call(tools, WORKSPACE_EDIT, bot, path=other_spelling, find="one", replace="1")

    assert isinstance(edit, Ok)


async def test_a_cleared_chat_has_read_nothing(tmp_path: Path) -> None:
    tools, path = tools_in(), written(tmp_path)
    await call(tools, WORKSPACE_WRITE, origin_in(tmp_path), path=path, text="one\n")
    cleared = origin_in(tmp_path, history_id="chat-1@12")

    edit = await call(tools, WORKSPACE_EDIT, cleared, path=path, find="one", replace="1")

    assert isinstance(edit, Failure)


def test_the_edit_tool_tells_the_model_to_read_first() -> None:
    assert "Read the file with `workspace_read` first" in _descriptions.WORKSPACE_EDIT
