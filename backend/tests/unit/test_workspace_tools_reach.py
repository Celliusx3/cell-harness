"""Which folders the workspace tools reach, and how `workspace_search` finds a text in them."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from harness.tools import Failure, Ok
from harness.tools.native.workspace import WORKSPACE_READ, WORKSPACE_SEARCH, WORKSPACE_WRITE
from tests.unit.test_workspace_tools import call, chat_folder, origin_in, text_of, tools_in


def own_folder(tmp_path: Path) -> Path:
    folder = tmp_path / "workspaces" / "own"
    folder.mkdir(parents=True, exist_ok=True)
    return folder.resolve()


async def test_in_a_group_the_bot_s_own_workspace_is_reached_too(tmp_path: Path) -> None:
    tools = tools_in()
    origin = replace(origin_in(tmp_path), own_workspace=own_folder(tmp_path))
    path = str(own_folder(tmp_path) / "mine.md")

    wrote = await call(tools, WORKSPACE_WRITE, origin, path=path, text="only mine\n")
    read = await call(tools, WORKSPACE_READ, origin, path=path)

    assert isinstance(wrote, Ok)
    assert text_of(read) == "1\tonly mine"


async def test_another_chat_s_workspace_is_out_of_reach(tmp_path: Path) -> None:
    other = tmp_path / "workspaces" / "chat-2"
    other.mkdir(parents=True)
    (other / "plan.md").write_text("theirs\n")

    read = await call(tools_in(), WORKSPACE_READ, origin_in(tmp_path), path=str(other / "plan.md"))

    assert isinstance(read, Failure)
    assert "theirs" not in text_of(read)


async def test_without_a_workspace_nothing_is_reached(tmp_path: Path) -> None:
    origin = replace(origin_in(tmp_path), workspace=None)
    folder = str(chat_folder(tmp_path))

    read = await call(tools_in(), WORKSPACE_READ, origin, path=folder)
    found = await call(tools_in(), WORKSPACE_SEARCH, origin, query="x")

    assert isinstance(read, Failure)
    assert isinstance(found, Failure)


async def test_a_search_returns_each_match_as_path_line_and_text(tmp_path: Path) -> None:
    tools, origin, folder = tools_in(), origin_in(tmp_path), chat_folder(tmp_path)
    await call(tools, WORKSPACE_WRITE, origin, path=str(folder / "notes/pdf.md"), text="hi\nPDFs\n")
    await call(tools, WORKSPACE_WRITE, origin, path=str(folder / "a.md"), text="pdf first\n")
    (folder / "b.bin").write_bytes(b"pdf\xff\xfe\x81")

    found = await call(tools, WORKSPACE_SEARCH, origin, query="pdf")
    under = await call(tools, WORKSPACE_SEARCH, origin, query="pdf", path=str(folder / "notes"))

    assert text_of(found) == f"{folder}/a.md:1: pdf first\n{folder}/notes/pdf.md:2: PDFs"
    assert text_of(under) == f"{folder}/notes/pdf.md:2: PDFs"


async def test_a_search_with_no_match_says_so(tmp_path: Path) -> None:
    tools, origin, folder = tools_in(), origin_in(tmp_path), chat_folder(tmp_path)
    await call(tools, WORKSPACE_WRITE, origin, path=str(folder / "a.md"), text="alpha\n")

    found = await call(tools, WORKSPACE_SEARCH, origin, query="beta")

    assert isinstance(found, Ok)
    assert text_of(found) == f"No text file in {folder} contains that text."


async def test_a_search_stops_at_100_matches_and_says_there_were_more(tmp_path: Path) -> None:
    tools, origin, folder = tools_in(), origin_in(tmp_path), chat_folder(tmp_path)
    text = "".join(f"hit {n}\n" for n in range(150))
    await call(tools, WORKSPACE_WRITE, origin, path=str(folder / "a.md"), text=text)

    shown = text_of(await call(tools, WORKSPACE_SEARCH, origin, query="HIT")).split("\n")

    assert shown[99] == f"{folder}/a.md:100: hit 99"
    assert shown[100] == ("More matches were left out. Search for a longer text to narrow them.")
    assert len(shown) == 101


async def test_a_search_for_empty_text_or_in_a_file_is_refused(tmp_path: Path) -> None:
    tools, origin, folder = tools_in(), origin_in(tmp_path), chat_folder(tmp_path)
    await call(tools, WORKSPACE_WRITE, origin, path=str(folder / "a.md"), text="alpha\n")

    empty = await call(tools, WORKSPACE_SEARCH, origin, query="")
    in_file = await call(tools, WORKSPACE_SEARCH, origin, query="a", path=str(folder / "a.md"))

    assert isinstance(empty, Failure)
    assert isinstance(in_file, Failure)
