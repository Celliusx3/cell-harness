"""`make_archive`: files in the chat files folder packed, in order, into one new archive."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from harness.tools import INVALID_ARGUMENTS, Failure, Ok, ToolOutcome
from harness.tools.native.files import make_archive_tool
from tests.unit.archive_fakes import chat_folder, drawn_png, making
from tests.unit.helpers import context_for
from tests.webapp import files_in


async def make(tmp_path: Path, paths: list[str], name: str) -> ToolOutcome:
    tool = make_archive_tool(files_in(tmp_path))
    return await tool.invoke(making(paths, name), context=context_for())


def drawn_pages(folder: Path, *names: str) -> list[str]:
    for shade, name in enumerate(names):
        (folder / name).write_bytes(drawn_png(shade))
    return [str(folder / name) for name in names]


def refusal(outcome: ToolOutcome) -> str:
    assert isinstance(outcome, Failure), outcome
    assert outcome.code == INVALID_ARGUMENTS
    return outcome.message


async def test_files_are_packed_in_the_given_order_under_their_position_and_name(
    tmp_path: Path,
) -> None:
    folder = chat_folder(tmp_path)
    pages = drawn_pages(folder, "page-c.png", "page-a.png", "page-b.png")

    outcome = await make(tmp_path, pages, "chapter.cbz")

    archive = folder / "chapter.cbz"
    assert isinstance(outcome, Ok) and outcome.text == str(archive)
    with zipfile.ZipFile(archive) as packed:
        assert packed.namelist() == ["001-page-c.png", "002-page-a.png", "003-page-b.png"]
        assert [packed.read(name) for name in packed.namelist()] == [
            drawn_png(0),
            drawn_png(1),
            drawn_png(2),
        ]
    assert sorted(path.name for path in folder.iterdir()) == [
        "chapter.cbz",
        "page-a.png",
        "page-b.png",
        "page-c.png",
    ]


async def test_the_archive_lands_beside_the_first_file(tmp_path: Path) -> None:
    first = chat_folder(tmp_path)
    second = first.parent / "other"
    second.mkdir()
    pages = [*drawn_pages(first, "1.png"), *drawn_pages(second, "2.png")]

    outcome = await make(tmp_path, pages, "chapter.zip")

    assert isinstance(outcome, Ok) and outcome.text == str(first / "chapter.zip")
    with zipfile.ZipFile(first / "chapter.zip") as packed:
        assert packed.namelist() == ["001-1.png", "002-2.png"]


@pytest.mark.parametrize("name", ["pages/chapter.cbz", "../chapter.cbz", "/tmp/chapter.cbz"])
async def test_a_name_with_a_folder_in_it_fails_and_writes_nothing(
    tmp_path: Path, name: str
) -> None:
    folder = chat_folder(tmp_path)
    pages = drawn_pages(folder, "1.png")

    assert name in refusal(await make(tmp_path, pages, name))
    assert [path.name for path in folder.iterdir()] == ["1.png"]
    assert not list(tmp_path.rglob("chapter.cbz"))


@pytest.mark.parametrize("name", ["chapter.rar", "chapter.cbz.png", "chapter", ".cbz"])
async def test_a_name_not_ending_in_cbz_or_zip_fails(tmp_path: Path, name: str) -> None:
    folder = chat_folder(tmp_path)
    pages = drawn_pages(folder, "1.png")

    assert name in refusal(await make(tmp_path, pages, name))
    assert [path.name for path in folder.iterdir()] == ["1.png"]


async def test_a_name_that_already_exists_fails_and_leaves_it_alone(tmp_path: Path) -> None:
    folder = chat_folder(tmp_path)
    pages = drawn_pages(folder, "1.png")
    existing = folder / "chapter.cbz"
    existing.write_bytes(b"the person's own")

    assert str(existing) in refusal(await make(tmp_path, pages, "chapter.cbz"))
    assert existing.read_bytes() == b"the person's own"


async def test_a_path_outside_this_chat_s_folder_fails_naming_it(tmp_path: Path) -> None:
    folder = chat_folder(tmp_path)
    outside = tmp_path / "secret.png"
    outside.write_bytes(drawn_png(9))
    pages = [*drawn_pages(folder, "1.png"), str(outside)]

    assert str(outside) in refusal(await make(tmp_path, pages, "chapter.cbz"))
    assert not (folder / "chapter.cbz").exists()


async def test_a_missing_path_fails_naming_it(tmp_path: Path) -> None:
    folder = chat_folder(tmp_path)
    missing = str(folder / "gone.png")

    assert missing in refusal(await make(tmp_path, [missing], "chapter.cbz"))
    assert list(folder.iterdir()) == []


async def test_packing_no_paths_is_invalid_arguments(tmp_path: Path) -> None:
    refusal(await make(tmp_path, [], "chapter.cbz"))


async def test_a_file_that_cannot_be_read_fails_and_leaves_no_partial_archive(
    tmp_path: Path,
) -> None:
    folder = chat_folder(tmp_path)
    pages = drawn_pages(folder, "1.png", "2.png")
    Path(pages[1]).chmod(0)

    outcome = await make(tmp_path, pages, "chapter.cbz")

    Path(pages[1]).chmod(0o600)
    assert isinstance(outcome, Failure) and "PermissionError" in outcome.message
    assert sorted(path.name for path in folder.iterdir()) == ["1.png", "2.png"]
