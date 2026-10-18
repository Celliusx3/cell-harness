"""`extract_archive`: an attached .zip or .cbz becomes numbered files beside it, once."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from harness.tools.definition import INVALID_ARGUMENTS, Failure, Ok, ToolOutcome
from harness.tools.native.files import extract_archive_tool
from harness.tools.native.files.archive import ArchiveError, copy_within
from tests.unit.archive_fakes import (
    UNPACK_LIMIT,
    Entry,
    chat_folder,
    drawn_png,
    every_file_under,
    extracting,
    link_entry,
    zipped,
)
from tests.unit.helpers import context_for
from tests.webapp import files_in

PAGES = (
    Entry("10.png", drawn_png(30)),
    Entry("2.png", drawn_png(20)),
    Entry("1.png", drawn_png(10)),
)


async def extract(tmp_path: Path, path: str, max_bytes: int = UNPACK_LIMIT) -> ToolOutcome:
    tool = extract_archive_tool(files_in(tmp_path), max_bytes)
    return await tool.invoke(extracting(path), context=context_for())


def written(outcome: ToolOutcome) -> list[Path]:
    assert isinstance(outcome, Ok), outcome
    count, *paths = outcome.text.splitlines()
    assert count == f"{len(paths)} files, in order:"
    return [Path(path) for path in paths]


def refusal(outcome: ToolOutcome) -> str:
    assert isinstance(outcome, Failure), outcome
    assert outcome.code == INVALID_ARGUMENTS
    return outcome.message


async def test_three_drawn_pages_unpack_to_numbered_files_in_natural_order(tmp_path: Path) -> None:
    archive = zipped(chat_folder(tmp_path) / "chapter.cbz", PAGES)

    paths = written(await extract(tmp_path, str(archive)))

    folder = archive.parent / "chapter-files"
    assert paths == [folder / "001.png", folder / "002.png", folder / "003.png"]
    assert [path.read_bytes() for path in paths] == [drawn_png(10), drawn_png(20), drawn_png(30)]


async def test_a_second_call_returns_the_same_paths_without_unpacking_again(
    tmp_path: Path,
) -> None:
    archive = zipped(chat_folder(tmp_path) / "chapter.cbz", PAGES)
    first = written(await extract(tmp_path, str(archive)))
    first[0].write_bytes(b"translated")

    second = written(await extract(tmp_path, str(archive)))

    assert second == first
    assert first[0].read_bytes() == b"translated"


async def test_an_entry_named_to_climb_out_lands_numbered_inside_the_folder(tmp_path: Path) -> None:
    archive = zipped(chat_folder(tmp_path) / "evil.cbz", [Entry("../../evil.png", drawn_png(1))])
    before = every_file_under(tmp_path)

    paths = written(await extract(tmp_path, str(archive)))

    assert paths == [archive.parent / "evil-files" / "001.png"]
    assert every_file_under(tmp_path) - before == {paths[0]}
    assert not list(tmp_path.rglob("evil.png"))


async def test_folders_mac_metadata_hidden_names_and_links_are_skipped(tmp_path: Path) -> None:
    archive = chat_folder(tmp_path) / "chapter.zip"
    with zipfile.ZipFile(archive, "w") as zipping:
        zipping.writestr("pages/", b"")
        zipping.writestr("__MACOSX/pages/._1.png", b"resource fork")
        zipping.writestr("__MACOSX/pages/1.png", drawn_png(20))
        zipping.writestr(".DS_Store", b"finder")
        zipping.writestr("pages/.hidden.png", drawn_png(5))
        zipping.writestr(link_entry("pages/0.png"), "/etc/passwd")
        zipping.writestr("pages/1.png", drawn_png(10))

    paths = written(await extract(tmp_path, str(archive)))

    assert paths == [archive.parent / "chapter-files" / "001.png"]
    assert paths[0].read_bytes() == drawn_png(10)


async def test_an_archive_declaring_more_than_the_limit_fails_and_writes_nothing(
    tmp_path: Path,
) -> None:
    archive = zipped(
        chat_folder(tmp_path) / "big.cbz", [Entry("1.png", b"a" * 100), Entry("2.png", b"b" * 100)]
    )

    message = refusal(await extract(tmp_path, str(archive), max_bytes=150))

    assert "200 bytes" in message and "150" in message
    assert list(archive.parent.iterdir()) == [archive]


def test_bytes_past_the_limit_stop_the_copy_before_they_are_written() -> None:
    target = io.BytesIO()

    with pytest.raises(ArchiveError):
        copy_within(io.BytesIO(b"x" * 20), target, 10)

    assert target.getvalue() == b""


def test_bytes_within_the_limit_are_copied_and_counted() -> None:
    target = io.BytesIO()

    assert copy_within(io.BytesIO(b"x" * 10), target, 10) == 10
    assert target.getvalue() == b"x" * 10


async def test_a_path_outside_this_chat_s_folder_fails_naming_it(tmp_path: Path) -> None:
    chat_folder(tmp_path)
    outside = zipped(tmp_path / "chapter.cbz", PAGES)

    message = refusal(await extract(tmp_path, str(outside)))

    assert str(outside) in message
    assert not (tmp_path / "chapter-files").exists()


async def test_a_link_in_this_chat_s_folder_to_an_archive_outside_it_fails(tmp_path: Path) -> None:
    outside = zipped(tmp_path / "chapter.cbz", PAGES)
    link = chat_folder(tmp_path) / "chapter.cbz"
    link.symlink_to(outside)

    message = refusal(await extract(tmp_path, str(link)))

    assert str(link) in message
    assert not (tmp_path / "chapter-files").exists()
    assert not (link.parent / "chapter-files").exists()


async def test_a_missing_file_fails_naming_it(tmp_path: Path) -> None:
    missing = chat_folder(tmp_path) / "gone.cbz"

    assert str(missing) in refusal(await extract(tmp_path, str(missing)))


async def test_a_file_that_is_not_a_zip_fails_naming_it(tmp_path: Path) -> None:
    page = chat_folder(tmp_path) / "page.cbz"
    page.write_bytes(drawn_png(1))

    message = refusal(await extract(tmp_path, str(page)))

    assert str(page) in message
    assert list(page.parent.iterdir()) == [page]


async def test_a_relative_path_fails_naming_it(tmp_path: Path) -> None:
    assert "upload/chapter.cbz" in refusal(await extract(tmp_path, "upload/chapter.cbz"))


async def test_an_archive_holding_no_files_fails_and_leaves_no_folder(tmp_path: Path) -> None:
    archive = zipped(
        chat_folder(tmp_path) / "empty.zip",
        [Entry("pages/", b""), Entry("__MACOSX/._1.png", b"fork")],
    )

    message = refusal(await extract(tmp_path, str(archive)))

    assert str(archive) in message
    assert list(archive.parent.iterdir()) == [archive]


async def test_an_entry_that_breaks_part_way_leaves_no_folder_behind(tmp_path: Path) -> None:
    archive = zipped(
        chat_folder(tmp_path) / "broken.cbz",
        [Entry("1.png", b"first page"), Entry("2.png", b"second page")],
    )
    archive.write_bytes(archive.read_bytes().replace(b"second page", b"SECOND PAGE"))

    message = refusal(await extract(tmp_path, str(archive)))

    assert str(archive) in message
    assert list(archive.parent.iterdir()) == [archive]
