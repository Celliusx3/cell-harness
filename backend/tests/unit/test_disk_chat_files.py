"""Each chat's folder on disk: what a write leaves behind, and which paths are inside it."""

from __future__ import annotations

import os
import stat
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from harness.files import DiskChatFileRepository

PNG_HEADER = b"\x89PNG\r\n\x1a\n"


def disk_in(tmp_path: Path) -> DiskChatFileRepository:
    return DiskChatFileRepository(tmp_path / "files")


async def chunks_of(*parts: bytes) -> AsyncIterator[bytes]:
    for part in parts:
        yield part


async def failing_after(part: bytes) -> AsyncIterator[bytes]:
    yield part
    raise RuntimeError("the upload broke off")


def everything_under(folder: Path) -> list[Path]:
    return sorted(folder.rglob("*")) if folder.exists() else []


async def test_a_write_lands_in_a_fresh_folder_of_the_chat_s_own(tmp_path) -> None:
    disk = disk_in(tmp_path)

    written = await disk.write("assistant", "page.png", chunks_of(PNG_HEADER))

    assert written.read_bytes() == PNG_HEADER
    assert written.parent.parent == disk.folder("assistant")


async def test_two_writes_of_one_name_keep_both(tmp_path) -> None:
    disk = disk_in(tmp_path)

    first = await disk.write("assistant", "a.txt", chunks_of(b"one"))
    second = await disk.write("assistant", "a.txt", chunks_of(b"two"))

    assert first != second
    assert first.read_bytes() == b"one"


async def test_the_folders_a_write_makes_are_readable_by_the_harness_alone(tmp_path) -> None:
    disk = disk_in(tmp_path)

    written = await disk.write("assistant", "a.txt", chunks_of(b"x"))

    for folder in (written.parent, disk.folder("assistant"), tmp_path / "files"):
        assert stat.S_IMODE(os.stat(folder).st_mode) == 0o700


async def test_a_write_that_fails_part_way_leaves_nothing(tmp_path) -> None:
    disk = disk_in(tmp_path)

    with pytest.raises(RuntimeError, match="broke off"):
        await disk.write("assistant", "big.bin", failing_after(PNG_HEADER))

    assert everything_under(disk.folder("assistant")) == []


@pytest.mark.parametrize("name", ["", "..", "a/b.png", "nul\x00.png"])
async def test_a_name_that_is_not_one_plain_name_is_never_written(tmp_path, name: str) -> None:
    with pytest.raises(ValueError, match="cannot name a file"):
        await disk_in(tmp_path).write("assistant", name, chunks_of(b"x"))

    assert everything_under(tmp_path / "files") == []


async def test_a_path_that_climbs_out_of_the_folder_is_not_the_chat_s(tmp_path) -> None:
    disk = disk_in(tmp_path)
    theirs = await disk.write("other", "page.png", chunks_of(PNG_HEADER))
    climbing = f"{disk.folder('assistant')}/../other/{theirs.parent.name}/page.png"

    assert disk.path_in("other", str(theirs)) == theirs
    assert disk.path_in("assistant", climbing) is None


async def test_a_link_in_the_folder_to_a_file_outside_it_is_not_the_chat_s(tmp_path) -> None:
    disk = disk_in(tmp_path)
    written = await disk.write("assistant", "page.png", chunks_of(PNG_HEADER))
    outside = tmp_path / "secret.txt"
    outside.write_text("no")
    link = written.with_name("link.txt")
    link.symlink_to(outside)

    assert disk.path_in("assistant", str(link)) is None


@pytest.mark.parametrize("path", ["/etc/hosts", "page.png", "", "/nul\x00byte"])
def test_a_path_outside_or_unreadable_is_not_the_chat_s(tmp_path, path: str) -> None:
    assert disk_in(tmp_path).path_in("assistant", path) is None


async def test_the_chat_s_folder_itself_is_not_a_file(tmp_path) -> None:
    disk = disk_in(tmp_path)
    await disk.write("assistant", "page.png", chunks_of(PNG_HEADER))

    assert disk.path_in("assistant", str(disk.folder("assistant"))) is None


def test_the_files_folder_exists_before_any_upload_readable_by_us_alone(tmp_path) -> None:
    disk = disk_in(tmp_path)

    disk.create_root()
    disk.create_root()

    root = tmp_path / "files"
    assert root.is_dir()
    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    assert everything_under(root) == []


@pytest.mark.parametrize("chat_id", ["", ".", "..", "a/b"])
def test_an_id_that_is_not_one_plain_name_has_no_folder(tmp_path, chat_id: str) -> None:
    with pytest.raises(ValueError, match="cannot name"):
        disk_in(tmp_path).folder(chat_id)
