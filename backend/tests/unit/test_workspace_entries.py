"""What a workspace listing leaves out, how it names its folder, and how it orders by name."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import PurePath

import pytest

from harness.files import WorkspaceEntry, WorkspacePathError
from harness.files.domain.models import relative_path, sorted_entries
from tests.webapp import files_in

CHANGED = datetime(2026, 1, 1, tzinfo=UTC)


def test_a_link_leading_outside_or_to_nothing_is_left_out_of_a_listing(tmp_path) -> None:
    files = files_in(tmp_path)
    workspace = files.workspace("bot-1")
    (workspace / "notes.txt").write_bytes(b"hi")
    (workspace / "away").symlink_to(files.workspace("bot-2"))
    (workspace / "gone").symlink_to(workspace / "missing.txt")
    (workspace / "near").symlink_to(workspace / "notes.txt")

    assert [(entry.name, entry.size) for entry in files.listing("bot-1", "").entries] == [
        ("near", 2),
        ("notes.txt", 2),
    ]


def test_a_link_to_a_folder_inside_the_workspace_is_listed_by_its_own_path(tmp_path) -> None:
    files = files_in(tmp_path)
    workspace = files.workspace("bot-1")
    (workspace / "out" / "pages").mkdir(parents=True)
    (workspace / "latest").symlink_to(workspace / "out")

    listing = files.listing("bot-1", "latest/")

    assert listing.path == "out"
    assert listing.workspace == str(workspace)


@pytest.mark.parametrize("path", ["notes.txt", "bad\x00name"])
def test_a_file_or_an_unreadable_path_is_not_a_folder_to_list(tmp_path, path) -> None:
    files = files_in(tmp_path)
    (files.workspace("bot-1") / "notes.txt").write_bytes(b"hi")

    with pytest.raises(WorkspacePathError):
        files.listing("bot-1", path)


def test_names_are_ordered_regardless_of_case_folders_first() -> None:
    entries = (
        WorkspaceEntry(name="b.txt", kind="file", size=1, modified=CHANGED),
        WorkspaceEntry(name="A.txt", kind="file", size=1, modified=CHANGED),
        WorkspaceEntry(name="zed", kind="folder", size=0, modified=CHANGED),
    )

    assert [entry.name for entry in sorted_entries(entries)] == ["zed", "A.txt", "b.txt"]


def test_the_workspace_itself_is_the_empty_path() -> None:
    assert relative_path(PurePath("/w"), PurePath("/w")) == ""
    assert relative_path(PurePath("/w"), PurePath("/w/a/b")) == "a/b"
