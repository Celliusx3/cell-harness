"""One folder of a chat's workspace, folders first; a path that leaves the workspace is refused."""

from __future__ import annotations

import pytest

from harness.files import WorkspaceEntry, WorkspacePathError
from tests.webapp import files_in


def test_a_folder_is_listed_folders_first_then_by_name_with_sizes(tmp_path) -> None:
    files = files_in(tmp_path)
    workspace = files.workspace("bot-1")
    (workspace / "zeta.txt").write_bytes(b"12345")
    (workspace / "alpha.txt").write_bytes(b"1")
    (workspace / "uploads").mkdir()

    listing = files.listing("bot-1", "")

    assert listing.path == ""
    assert listing.entries == (
        WorkspaceEntry(name="uploads", kind="folder", size=0),
        WorkspaceEntry(name="alpha.txt", kind="file", size=1),
        WorkspaceEntry(name="zeta.txt", kind="file", size=5),
    )


def test_a_folder_inside_is_listed_by_its_relative_path(tmp_path) -> None:
    files = files_in(tmp_path)
    (files.workspace("bot-1") / "out" / "pages").mkdir(parents=True)

    assert files.listing("bot-1", "out").entries == (
        WorkspaceEntry(name="pages", kind="folder", size=0),
    )


@pytest.mark.parametrize("path", ["..", "../bot-2", "out/../../bot-2", "/etc", "missing"])
def test_a_path_that_leaves_the_workspace_or_is_missing_is_refused(tmp_path, path) -> None:
    files = files_in(tmp_path)
    files.workspace("bot-1")
    (files.workspace("bot-1") / "out").mkdir()
    files.workspace("bot-2")

    with pytest.raises(WorkspacePathError):
        files.listing("bot-1", path)


def test_a_link_that_leaves_the_workspace_is_refused(tmp_path) -> None:
    files = files_in(tmp_path)
    (files.workspace("bot-1") / "away").symlink_to(files.workspace("bot-2"))

    with pytest.raises(WorkspacePathError):
        files.listing("bot-1", "away")


def test_a_chat_with_no_workspace_yet_lists_empty_and_makes_no_folder(tmp_path) -> None:
    listing = files_in(tmp_path).listing("bot-9", "")

    assert listing.entries == ()
    assert not (tmp_path / "files" / "workspaces" / "bot-9").exists()
