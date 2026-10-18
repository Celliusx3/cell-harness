"""pages unpacks a comic once, lists its parts and saves each part as a JPEG of 5 MiB or less."""

from __future__ import annotations

import io
import random
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from comic import ComicError
from comic.chapter.work import WorkFolder
from comic.steps import page_of
from comic.steps import view as view_module
from comic.steps.pages import list_pages
from comic.steps.view import jpeg_of


def comic(tmp_path: Path) -> Path:
    """A .cbz of a tall page and a short one."""
    source = tmp_path / "ch1.cbz"
    with zipfile.ZipFile(source, "w") as archive:
        for name, size in (("p10.png", (400, 400)), ("p2.png", (400, 1800))):
            Image.new("RGB", size, (255, 255, 255)).save(tmp_path / name)
            archive.write(tmp_path / name, name)
            (tmp_path / name).unlink()
        archive.writestr("__MACOSX/p1.png", b"")
    return source


def test_a_comic_is_unpacked_in_natural_order_and_its_parts_counted(tmp_path: Path) -> None:
    result = list_pages(str(comic(tmp_path)))

    assert result.work == str(tmp_path / "ch1-english")
    assert [(page.page, page.parts) for page in result.pages] == [("001.png", 3), ("002.png", 1)]
    assert (tmp_path / "ch1-english" / "pages.json").is_file()


def test_a_listed_comic_is_listed_again_without_unpacking(tmp_path: Path) -> None:
    source = comic(tmp_path)
    first = list_pages(str(source))
    source.unlink()
    source.write_bytes(b"")

    assert list_pages(str(source)) == first


def test_a_comic_with_no_pages_is_refused(tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()

    with pytest.raises(ComicError, match="no .png, .jpg, .jpeg, .webp pages in"):
        list_pages(str(tmp_path / "empty"))


def test_a_comic_that_is_not_there_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ComicError, match="ch9.cbz does not exist"):
        list_pages(str(tmp_path / "ch9.cbz"))


def test_each_part_of_a_page_is_saved_as_its_own_jpeg_top_to_bottom(tmp_path: Path) -> None:
    [tall, short] = list_pages(str(comic(tmp_path))).pages

    sizes = [Image.open(view).size for view in tall.views]
    assert sizes == [(400, 1000), (400, 1000), (400, 800)]
    assert [Image.open(view).format for view in tall.views] == ["JPEG"] * 3
    assert [Image.open(view).size for view in short.views] == [(400, 400)]


def test_a_view_deleted_after_listing_is_saved_again(tmp_path: Path) -> None:
    source = comic(tmp_path)
    [page, _] = list_pages(str(source)).pages
    Path(page.views[1]).unlink()

    [again, _] = list_pages(str(source)).pages

    assert again.views == page.views
    assert all(Path(view).is_file() for view in again.views)


def test_a_part_too_large_for_a_view_is_downscaled_until_it_fits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(view_module, "MAX_IMAGE_BYTES", 20_000)
    noise = random.Random(1)
    image = Image.frombytes("RGB", (300, 300), noise.randbytes(300 * 300 * 3))

    jpeg = jpeg_of(image)

    assert len(jpeg) <= 20_000
    assert Image.open(io.BytesIO(jpeg)).width < 300


def test_a_page_the_work_folder_lacks_is_refused(tmp_path: Path) -> None:
    work = WorkFolder(Path(list_pages(str(comic(tmp_path))).work))

    with pytest.raises(ComicError, match="003.png is not a page in"):
        page_of(work, "003.png")
