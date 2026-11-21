"""The workspace tools, called through `ToolService.dispatch` as a bot's turn calls them."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from harness.files import WorkspaceTextRepository, WorkspaceTextService
from harness.llm import ToolCall
from harness.tools import CallOrigin, Failure, Ok, ToolOutcome, ToolService
from harness.tools.native.workspace import (
    WORKSPACE_EDIT,
    WORKSPACE_READ,
    WORKSPACE_WRITE,
    workspace_tools,
)
from tests.unit.helpers import no_approvals, no_progress


def chat_folder(tmp_path: Path) -> Path:
    """The chat's workspace a call is made in, made and resolved."""
    folder = tmp_path / "workspaces" / "chat-1"
    folder.mkdir(parents=True, exist_ok=True)
    return folder.resolve()


def origin_in(tmp_path: Path, history_id: str = "chat-1@0") -> CallOrigin:
    """A call made in the chat's workspace, from `history_id`'s model history."""
    return CallOrigin(
        bot_id="b",
        conversation_id="chat-1",
        mode="auto",
        workspace=chat_folder(tmp_path),
        own_workspace=None,
        history_id=history_id,
    )


def tools_in() -> ToolService:
    service = WorkspaceTextService(WorkspaceTextRepository())
    return ToolService(workspace_tools(service), approvals=no_approvals())


async def call(
    tools: ToolService, name: str, origin: CallOrigin, **arguments: object
) -> ToolOutcome:
    """`name` called with `arguments` from `origin`."""
    request = ToolCall(id="c1", name=name, arguments=json.dumps(arguments))
    return await tools.dispatch(request, progress=no_progress, approved=False, origin=origin)


def text_of(outcome: ToolOutcome) -> str:
    assert isinstance(outcome, Ok | Failure)
    return outcome.content[0].text


async def test_a_written_file_reads_back_numbered_and_is_on_disk(tmp_path: Path) -> None:
    tools, origin = tools_in(), origin_in(tmp_path)
    path = str(chat_folder(tmp_path) / "notes" / "notes.md")

    wrote = await call(tools, WORKSPACE_WRITE, origin, path=path, text="alpha\nbeta\n")
    read = await call(tools, WORKSPACE_READ, origin, path=path)

    assert text_of(wrote) == f"Wrote {path}."
    assert text_of(read) == "1\talpha\n2\tbeta"
    assert Path(path).read_text() == "alpha\nbeta\n"


async def test_a_folder_reads_as_its_entries_folders_first(tmp_path: Path) -> None:
    tools, origin, folder = tools_in(), origin_in(tmp_path), chat_folder(tmp_path)
    empty = await call(tools, WORKSPACE_READ, origin, path=str(folder))
    for name in ("b.md", "a/c.md", "Z/d.md"):
        await call(tools, WORKSPACE_WRITE, origin, path=str(folder / name), text="")

    listed = await call(tools, WORKSPACE_READ, origin, path=str(folder))

    assert text_of(empty) == f"The folder {folder} is empty."
    assert text_of(listed) == "a/\nZ/\nb.md"


async def test_a_path_outside_the_workspace_is_an_error_and_writes_nothing(
    tmp_path: Path,
) -> None:
    tools, origin, folder = tools_in(), origin_in(tmp_path), chat_folder(tmp_path)

    climbed = await call(tools, WORKSPACE_WRITE, origin, path=str(folder / ".." / "x"), text="x")
    relative = await call(tools, WORKSPACE_WRITE, origin, path="notes.md", text="x")
    unnamed = await call(tools, WORKSPACE_WRITE, origin, path=f"{folder}/a\x00b", text="x")
    elsewhere = await call(tools, WORKSPACE_READ, origin, path="/etc/hosts")

    for outcome in (climbed, relative, unnamed, elsewhere):
        assert isinstance(outcome, Failure)
        assert text_of(outcome).startswith("error: ")
    assert "/etc/hosts is not inside a workspace you were told about" in text_of(elsewhere)
    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []


async def test_a_symlink_out_of_the_workspace_is_refused(tmp_path: Path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("secret")
    link = chat_folder(tmp_path) / "link.txt"
    link.symlink_to(secret)

    read = await call(tools_in(), WORKSPACE_READ, origin_in(tmp_path), path=str(link))

    assert isinstance(read, Failure)
    assert "secret" not in text_of(read).replace(str(secret), "")


async def test_an_edit_whose_find_is_missing_or_twice_leaves_the_file(tmp_path: Path) -> None:
    tools, origin = tools_in(), origin_in(tmp_path)
    path = str(chat_folder(tmp_path) / "a.md")
    await call(tools, WORKSPACE_WRITE, origin, path=path, text="one\none\ntwo\n")

    missing = await call(tools, WORKSPACE_EDIT, origin, path=path, find="three", replace="3")
    twice = await call(tools, WORKSPACE_EDIT, origin, path=path, find="one", replace="1")
    empty = await call(tools, WORKSPACE_EDIT, origin, path=path, find="", replace="1")

    assert isinstance(missing, Failure) and isinstance(twice, Failure)
    assert isinstance(empty, Failure)
    assert "appears 0 times" in text_of(missing)
    assert "appears 2 times" in text_of(twice)
    assert Path(path).read_text() == "one\none\ntwo\n"


async def test_an_edit_replaces_the_one_find(tmp_path: Path) -> None:
    tools, origin = tools_in(), origin_in(tmp_path)
    path = str(chat_folder(tmp_path) / "a.md")
    await call(tools, WORKSPACE_WRITE, origin, path=path, text="one\ntwo\n")

    edit = await call(tools, WORKSPACE_EDIT, origin, path=path, find="two", replace="2")

    assert text_of(edit) == f"Edited {path}."
    assert Path(path).read_text() == "one\n2\n"


async def test_an_edit_of_a_missing_file_is_an_error(tmp_path: Path) -> None:
    path = str(chat_folder(tmp_path) / "no.md")

    edit = await call(
        tools_in(), WORKSPACE_EDIT, origin_in(tmp_path), path=path, find="a", replace="b"
    )

    assert isinstance(edit, Failure)


async def test_two_edits_at_once_both_land(tmp_path: Path) -> None:
    tools, origin = tools_in(), origin_in(tmp_path)
    path = str(chat_folder(tmp_path) / "plan.md")
    await call(tools, WORKSPACE_WRITE, origin, path=path, text="# A\nfirst\n\n# B\nsecond\n")

    await asyncio.gather(
        call(tools, WORKSPACE_EDIT, origin, path=path, find="first", replace="1st"),
        call(tools, WORKSPACE_EDIT, origin, path=path, find="second", replace="2nd"),
    )

    assert Path(path).read_text() == "# A\n1st\n\n# B\n2nd\n"


async def test_writing_over_an_existing_file_is_refused(tmp_path: Path) -> None:
    tools, origin = tools_in(), origin_in(tmp_path)
    path = str(chat_folder(tmp_path) / "a.md")
    await call(tools, WORKSPACE_WRITE, origin, path=path, text="first")

    again = await call(tools, WORKSPACE_WRITE, origin, path=path, text="second")

    assert isinstance(again, Failure)
    assert "already exists" in text_of(again)
    assert Path(path).read_text() == "first"


async def test_a_range_reads_both_ends_included_and_a_bad_one_is_an_error(
    tmp_path: Path,
) -> None:
    tools, origin = tools_in(), origin_in(tmp_path)
    path = str(chat_folder(tmp_path) / "a.md")
    await call(tools, WORKSPACE_WRITE, origin, path=path, text="1\n2\n3\n4\n5\n")

    read = await call(tools, WORKSPACE_READ, origin, path=path, start_line=2, end_line=4)
    past = await call(tools, WORKSPACE_READ, origin, path=path, start_line=9)

    assert text_of(read) == "2\t2\n3\t3\n4\t4"
    assert isinstance(past, Failure)


async def test_an_empty_file_reads_as_empty(tmp_path: Path) -> None:
    tools, origin = tools_in(), origin_in(tmp_path)
    path = str(chat_folder(tmp_path) / "a.md")
    await call(tools, WORKSPACE_WRITE, origin, path=path, text="")

    assert text_of(await call(tools, WORKSPACE_READ, origin, path=path)) == f"{path} is empty."


async def test_a_read_stops_at_2000_lines_and_says_where(tmp_path: Path) -> None:
    tools, origin = tools_in(), origin_in(tmp_path)
    path = str(chat_folder(tmp_path) / "long.md")
    await call(
        tools, WORKSPACE_WRITE, origin, path=path, text="".join(f"l{n}\n" for n in range(2500))
    )

    shown = text_of(await call(tools, WORKSPACE_READ, origin, path=path)).split("\n")

    assert shown[1999] == "2000\tl1999"
    assert shown[2000] == "Stopped at line 2000 of 2500 lines."


async def test_a_file_that_is_not_utf8_is_an_error_saying_it_is_not_text(tmp_path: Path) -> None:
    binary = chat_folder(tmp_path) / "image.bin"
    binary.write_bytes(b"\xff\xfe\x00\x81")

    read = await call(tools_in(), WORKSPACE_READ, origin_in(tmp_path), path=str(binary))

    assert isinstance(read, Failure)
    assert text_of(read) == f"error: {binary} is not a UTF-8 text file"
