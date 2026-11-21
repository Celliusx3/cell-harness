"""The workspace tools on a real disk: modes kept, size capped, disk errors typed, no links."""

from __future__ import annotations

import stat
import threading
from pathlib import Path

import pytest

from harness.files import WorkspaceFileError, WorkspaceTextRepository, WorkspaceTextService
from harness.files.domain.text_edit import MAX_TEXT_BYTES
from harness.files.repository.workspace_text_repository import Located
from harness.tools import Failure
from harness.tools.native.workspace import (
    WORKSPACE_EDIT,
    WORKSPACE_READ,
    WORKSPACE_WRITE,
)
from tests.unit.test_workspace_tools import call, chat_folder, origin_in, text_of, tools_in


def big_file(path: Path) -> Path:
    """A file one byte past the cap, made sparse so the test stays fast."""
    with path.open("wb") as handle:
        handle.truncate(MAX_TEXT_BYTES + 1)
    return path


@pytest.mark.parametrize("mode", [0o644, 0o755])
async def test_an_edit_keeps_the_file_s_mode(tmp_path: Path, mode: int) -> None:
    tools, origin = tools_in(), origin_in(tmp_path)
    path = chat_folder(tmp_path) / "run.sh"
    await call(tools, WORKSPACE_WRITE, origin, path=str(path), text="echo one\n")
    path.chmod(mode)
    await call(tools, WORKSPACE_READ, origin, path=str(path))

    await call(tools, WORKSPACE_EDIT, origin, path=str(path), find="one", replace="two")

    assert path.read_text() == "echo two\n"
    assert stat.S_IMODE(path.stat().st_mode) == mode


async def test_a_file_past_the_cap_is_refused_by_read_and_edit(tmp_path: Path) -> None:
    tools, origin = tools_in(), origin_in(tmp_path)
    path = big_file(chat_folder(tmp_path) / "big.txt")

    read = await call(tools, WORKSPACE_READ, origin, path=str(path))
    edit = await call(tools, WORKSPACE_EDIT, origin, path=str(path), find="a", replace="b")

    for outcome in (read, edit):
        assert isinstance(outcome, Failure)
        assert "too large" in text_of(outcome)


async def test_a_write_past_the_cap_is_refused_and_makes_no_folder(tmp_path: Path) -> None:
    tools, origin = tools_in(), origin_in(tmp_path)
    path = chat_folder(tmp_path) / "new" / "big.txt"

    wrote = await call(
        tools, WORKSPACE_WRITE, origin, path=str(path), text="x" * (MAX_TEXT_BYTES + 1)
    )

    assert isinstance(wrote, Failure)
    assert "too large" in text_of(wrote)
    assert not path.parent.exists()


async def test_an_unreadable_file_is_a_plain_error(tmp_path: Path) -> None:
    path = chat_folder(tmp_path) / "locked.md"
    path.write_text("secret")
    path.chmod(0)

    read = await call(tools_in(), WORKSPACE_READ, origin_in(tmp_path), path=str(path))

    path.chmod(0o600)
    assert isinstance(read, Failure)
    assert text_of(read) == f"error: {path} could not be used on disk (Permission denied)"


async def test_a_write_under_a_file_is_a_plain_error(tmp_path: Path) -> None:
    folder = chat_folder(tmp_path)
    (folder / "plain.md").write_text("x")
    path = folder / "plain.md" / "inner" / "a.md"

    wrote = await call(tools_in(), WORKSPACE_WRITE, origin_in(tmp_path), path=str(path), text="x")

    assert isinstance(wrote, Failure)
    assert "could not be used on disk" in text_of(wrote)


async def test_disk_work_runs_off_the_event_loop(tmp_path: Path) -> None:
    seen: list[int] = []

    class Watched(WorkspaceTextRepository):
        def read_text(self, target: Path) -> str:
            seen.append(threading.get_ident())
            return super().read_text(target)

    texts = WorkspaceTextService(Watched())
    path = chat_folder(tmp_path) / "a.md"
    path.write_text("one\n")

    await texts.read((chat_folder(tmp_path),), str(path), "h")

    assert seen and threading.get_ident() not in seen


def test_a_link_given_to_read_is_refused(tmp_path: Path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("secret")
    link = chat_folder(tmp_path) / "link.txt"
    link.symlink_to(secret)

    with pytest.raises(WorkspaceFileError):
        WorkspaceTextRepository().read_text(link)


def test_a_folder_swapped_for_a_link_out_is_refused_on_create(tmp_path: Path) -> None:
    root, outside = chat_folder(tmp_path), tmp_path / "outside"
    outside.mkdir()
    (root / "notes").symlink_to(outside)

    with pytest.raises(WorkspaceFileError):
        WorkspaceTextRepository().create(Located(path=root / "notes" / "a.md", root=root), "x")

    assert list(outside.iterdir()) == []


def test_a_new_file_is_not_made_through_a_dangling_link(tmp_path: Path) -> None:
    root = chat_folder(tmp_path)
    (root / "a.md").symlink_to(tmp_path / "nowhere.md")

    with pytest.raises(WorkspaceFileError):
        WorkspaceTextRepository().create(Located(path=root / "a.md", root=root), "x")

    assert not (tmp_path / "nowhere.md").exists()


async def test_a_crlf_file_is_edited_with_a_lf_find(tmp_path: Path) -> None:
    tools, origin = tools_in(), origin_in(tmp_path)
    path = chat_folder(tmp_path) / "win.txt"
    path.write_bytes(b"one\r\ntwo\r\nthree\r\n")
    await call(tools, WORKSPACE_READ, origin, path=str(path))

    edit = await call(
        tools, WORKSPACE_EDIT, origin, path=str(path), find="one\ntwo", replace="1\n2"
    )

    assert text_of(edit) == f"Edited {path}."
    assert path.read_bytes() == b"1\r\n2\r\nthree\r\n"
