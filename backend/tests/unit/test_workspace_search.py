"""Finding a text in a workspace's files: every line that holds it, ignoring case, in order."""

from __future__ import annotations

import itertools
from pathlib import Path

from harness.files.domain.search import SHOWN_MATCHES, Match, TextFile, matches
from harness.files.domain.text_edit import MAX_TEXT_BYTES
from harness.tools.native.workspace import WORKSPACE_SEARCH
from harness.tools.native.workspace._found import SHOWN_LINE_CHARS
from tests.unit.test_workspace_tools import call, chat_folder, origin_in, text_of, tools_in


def test_a_line_that_holds_the_text_is_a_match_with_its_number() -> None:
    files = [TextFile(path="notes.md", text="alpha\nthe client wants PDFs\ngamma\n")]

    assert matches(files, "PDF") == (
        Match(path="notes.md", number=2, line="the client wants PDFs"),
    )


def test_case_is_ignored_and_the_line_is_kept_as_is() -> None:
    files = [TextFile(path="a.md", text="Send A PDF\n")]

    assert matches(files, "pdf") == (Match(path="a.md", number=1, line="Send A PDF"),)


def test_matches_follow_the_files_then_the_lines() -> None:
    files = [TextFile(path="a.md", text="x1\ny\nx2\n"), TextFile(path="b.md", text="x3\n")]

    found = matches(files, "x")

    assert [(m.path, m.number) for m in found] == [("a.md", 1), ("a.md", 3), ("b.md", 1)]


def test_no_line_holding_the_text_is_no_match() -> None:
    assert matches([TextFile(path="a.md", text="alpha\n")], "beta") == ()


def test_matching_stops_one_past_what_is_shown() -> None:
    endless = itertools.repeat(TextFile(path="a.md", text="x\n"))

    assert len(matches(endless, "x")) == SHOWN_MATCHES + 1


async def test_a_search_skips_files_past_the_cap_and_unreadable_ones(tmp_path: Path) -> None:
    folder = chat_folder(tmp_path)
    (folder / "ok.md").write_text("needle\n")
    with (folder / "big.md").open("w") as handle:
        handle.write("needle\n")
        handle.truncate(MAX_TEXT_BYTES + 1)
    locked = folder / "locked.md"
    locked.write_text("needle\n")
    locked.chmod(0)

    found = await call(tools_in(), WORKSPACE_SEARCH, origin_in(tmp_path), query="needle")

    locked.chmod(0o600)
    assert text_of(found) == f"{folder / 'ok.md'}:1: needle"


async def test_a_long_matching_line_is_cut(tmp_path: Path) -> None:
    folder = chat_folder(tmp_path)
    (folder / "a.md").write_text("needle" + "x" * 1000 + "\n")

    found = text_of(await call(tools_in(), WORKSPACE_SEARCH, origin_in(tmp_path), query="needle"))

    shown = found.removeprefix(f"{folder / 'a.md'}:1: ")
    assert len(shown) == SHOWN_LINE_CHARS + 1
    assert shown.endswith("…")
