"""A file or a folder in a chat's workspace is deleted; the workspace itself and outside are not."""

from __future__ import annotations

import pytest

from harness.files import WorkspacePathError
from tests.webapp import files_in


def test_a_file_and_a_folder_with_everything_in_it_are_deleted(tmp_path) -> None:
    files = files_in(tmp_path)
    workspace = files.workspace("bot-1")
    (workspace / "old.txt").write_bytes(b"x")
    (workspace / "uploads" / "token").mkdir(parents=True)
    (workspace / "uploads" / "token" / "page.png").write_bytes(b"x")

    files.delete_path("bot-1", "old.txt")
    files.delete_path("bot-1", "uploads")

    assert list(workspace.iterdir()) == []


@pytest.mark.parametrize("path", ["", ".", "..", "../bot-2", "/etc/hosts", "missing.txt"])
def test_the_workspace_itself_a_path_outside_or_a_missing_one_is_refused(tmp_path, path) -> None:
    files = files_in(tmp_path)
    workspace = files.workspace("bot-1")
    other = files.workspace("bot-2") / "keep.txt"
    other.write_bytes(b"x")

    with pytest.raises(WorkspacePathError):
        files.delete_path("bot-1", path)

    assert workspace.is_dir() and other.exists()


def test_a_link_out_of_the_workspace_is_deleted_as_a_link_leaving_its_target(tmp_path) -> None:
    files = files_in(tmp_path)
    target = files.workspace("bot-2") / "keep.txt"
    target.write_bytes(b"x")
    link = files.workspace("bot-1") / "away"
    link.symlink_to(target)

    files.delete_path("bot-1", "away")

    assert not link.is_symlink() and target.exists()
