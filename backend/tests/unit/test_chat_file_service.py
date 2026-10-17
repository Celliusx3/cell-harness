"""The rules a chat's files keep: a usable name, the upload limit, the type, and whose a path is."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from harness.files import ChatFile, FileTooLarge, UnsafeFileName
from tests.webapp import files_in

PNG_HEADER = b"\x89PNG\r\n\x1a\n"


async def chunks_of(*parts: bytes) -> AsyncIterator[bytes]:
    for part in parts:
        yield part


def everything_under(folder: Path) -> list[Path]:
    return sorted(folder.rglob("*")) if folder.exists() else []


async def test_an_upload_is_saved_with_its_name_type_and_size(tmp_path) -> None:
    saved = await files_in(tmp_path).save("assistant", "page.png", chunks_of(PNG_HEADER))

    assert Path(saved.path).read_bytes() == PNG_HEADER
    assert saved == ChatFile(path=saved.path, name="page.png", media_type="image/png", size=8)


async def test_a_name_with_folders_in_it_is_saved_as_its_last_part(tmp_path) -> None:
    saved = await files_in(tmp_path).save("assistant", "../../x.png", chunks_of(PNG_HEADER))

    assert saved.name == "x.png"
    assert Path(saved.path).parent.parent == tmp_path.resolve() / "files" / "assistant"


@pytest.mark.parametrize("name", ["", ".", "..", "a/..", "nul\x00.png"])
async def test_a_name_with_nothing_to_save_under_is_refused(tmp_path, name: str) -> None:
    with pytest.raises(UnsafeFileName):
        await files_in(tmp_path).save("assistant", name, chunks_of(b"x"))

    assert everything_under(tmp_path / "files") == []


async def test_an_upload_over_the_limit_leaves_nothing_on_disk(tmp_path) -> None:
    files = files_in(tmp_path, max_bytes=8)

    with pytest.raises(FileTooLarge, match="8 bytes"):
        await files.save("assistant", "big.bin", chunks_of(PNG_HEADER, b"!"))

    assert everything_under(tmp_path / "files" / "assistant") == []


async def test_an_upload_of_exactly_the_limit_is_kept(tmp_path) -> None:
    saved = await files_in(tmp_path, max_bytes=8).save(
        "assistant", "edge.png", chunks_of(PNG_HEADER)
    )

    assert saved.size == 8


async def test_a_file_with_no_known_extension_is_an_octet_stream(tmp_path) -> None:
    saved = await files_in(tmp_path).save("assistant", "notes", chunks_of(b"x"))

    assert saved.media_type == "application/octet-stream"


async def test_a_file_in_the_chat_s_folder_is_the_chat_s(tmp_path) -> None:
    files = files_in(tmp_path)
    saved = await files.save("assistant", "page.png", chunks_of(PNG_HEADER))

    assert files.file_at("assistant", saved.path) == saved


async def test_a_file_in_another_chat_s_folder_is_not_this_chat_s(tmp_path) -> None:
    files = files_in(tmp_path)
    theirs = await files.save("other", "page.png", chunks_of(PNG_HEADER))

    assert files.file_at("assistant", theirs.path) is None
