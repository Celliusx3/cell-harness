"""cleanup leaves only the archive in the work folder, and touches nothing outside it."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from comic import ComicError
from comic.steps.cleanup import clean_up_work_folder
from comic.steps.pages import list_pages


def work_folder(tmp_path: Path) -> Path:
    """A listed one-page comic whose work folder holds clean and English pages and an archive."""
    Image.new("RGB", (200, 300), "white").save(tmp_path / "ch1.png")
    work = Path(list_pages(str(tmp_path / "ch1.png")).work)
    for folder in ("clean", "english", "english/old"):
        (work / folder).mkdir()
    (work / "clean" / "001.png").write_bytes(b"c" * 10)
    (work / "english" / "001.png").write_bytes(b"e" * 20)
    (work / "english" / "old" / "001.png").write_bytes(b"o" * 30)
    (work / "english" / "ch1-english.cbz").write_bytes(b"archive")
    return work


def everything_under(folder: Path) -> list[Path]:
    return sorted(folder.rglob("*"))


def test_the_archive_stays_at_its_path_and_the_rest_goes(tmp_path: Path) -> None:
    work = work_folder(tmp_path)
    archive = work / "english" / "ch1-english.cbz"
    doomed = [p for p in everything_under(work) if p.is_file() and p != archive]
    sizes = sum(p.stat().st_size for p in doomed)

    result = clean_up_work_folder(str(work), str(archive))

    assert everything_under(work) == [work / "english", archive]
    assert archive.read_bytes() == b"archive"
    assert result.kept == str(archive)
    assert (result.removed_files, result.freed_bytes) == (len(doomed), sizes)


def test_a_link_out_of_the_work_folder_is_removed_and_never_followed(tmp_path: Path) -> None:
    work = work_folder(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "precious.png").write_bytes(b"keep me")
    (work / "to-folder").symlink_to(elsewhere, target_is_directory=True)
    (work / "english" / "to-file").symlink_to(elsewhere / "precious.png")
    archive = work / "english" / "ch1-english.cbz"

    clean_up_work_folder(str(work), str(archive))

    assert everything_under(work) == [work / "english", archive]
    assert (elsewhere / "precious.png").read_bytes() == b"keep me"


def test_a_keep_outside_the_work_folder_is_refused_and_nothing_is_deleted(
    tmp_path: Path,
) -> None:
    work = work_folder(tmp_path)
    before = everything_under(work)

    with pytest.raises(ComicError, match="ch1.png is not inside the work folder"):
        clean_up_work_folder(str(work), str(tmp_path / "ch1.png"))

    assert everything_under(work) == before


def test_a_keep_that_is_not_there_is_refused(tmp_path: Path) -> None:
    work = work_folder(tmp_path)
    before = everything_under(work)

    with pytest.raises(ComicError, match="ch9.cbz does not exist"):
        clean_up_work_folder(str(work), str(work / "ch9.cbz"))

    assert everything_under(work) == before


@pytest.mark.parametrize("name", ["english", "link.cbz"])
def test_a_keep_that_is_a_folder_or_a_link_is_refused(tmp_path: Path, name: str) -> None:
    work = work_folder(tmp_path)
    (work / "link.cbz").symlink_to(work / "english" / "ch1-english.cbz")

    with pytest.raises(ComicError, match=f"{name} is not a file"):
        clean_up_work_folder(str(work), str(work / name))


def test_a_folder_list_pages_did_not_make_is_never_emptied(tmp_path: Path) -> None:
    work_folder(tmp_path)
    before = everything_under(tmp_path)

    with pytest.raises(ComicError, match="holds no pages.json"):
        clean_up_work_folder(str(tmp_path), str(tmp_path / "ch1.png"))

    assert everything_under(tmp_path) == before
