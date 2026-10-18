"""write erases and letters a page through PhotoCraft, counts its attempts and closes its pages."""

from __future__ import annotations

import threading
import time
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from comic import ComicError
from comic.chapter.pages import Item
from comic.chapter.work import WorkFolder
from comic.connection import PhotoCraftError, connected
from comic.document import BatchStep, Document
from comic.lock import held
from comic.models import WriteResult
from comic.steps.pages import list_pages
from comic.steps.write import PhotoCraftAccess, write_page
from comic.tests.unit.fake_photocraft import TOKEN, FakePhotoCraft
from comic.tests.unit.one_bubble import bubble_items

TOO_LONG = "So many words that no bubble on this page could ever hold them all on one line"
ROUGH_BOX_2D = (469, 500, 656, 750)


def work_of(comic: Path) -> WorkFolder:
    return WorkFolder(Path(list_pages(str(comic)).work))


def test_a_written_page_is_erased_and_every_photocraft_page_is_closed(
    bubble_comic: Path, photocraft: FakePhotoCraft, access: PhotoCraftAccess
) -> None:
    work = work_of(bubble_comic)

    result = write_page(access, work, "001.png", bubble_items("Hi!"))

    assert (result.attempt, result.cut_off, result.spills, result.left_over) == (1, [], [], [])
    assert result.english == str(work.english_png("001.png"))
    assert [Path(view).is_file() for view in result.views] == [True]
    assert photocraft.documents == []
    assert all(batch["stopOnError"] is False for batch in photocraft.batches)


def test_a_line_that_does_not_fit_at_the_smallest_size_is_cut_off(
    bubble_comic: Path, access: PhotoCraftAccess
) -> None:
    result = write_page(access, work_of(bubble_comic), "001.png", bubble_items(TOO_LONG))

    assert result.cut_off == [TOO_LONG]


def test_a_fill_photocraft_refuses_names_the_item_and_counts_no_attempt(
    bubble_comic: Path, access: PhotoCraftAccess
) -> None:
    refusing = FakePhotoCraft(frozenset({"edit.fill"}))
    work = work_of(bubble_comic)

    with pytest.raises(ComicError, match=r"001.png: PhotoCraft could not erase 'Hi!' \(command"):
        write_page(replace(access, addr=refusing.addr), work, "001.png", bubble_items("Hi!"))

    assert refusing.documents == []
    assert not work.translations_json().exists()


def test_a_batch_photocraft_stopped_short_is_refused_and_its_page_closed(
    bubble_comic: Path, access: PhotoCraftAccess
) -> None:
    stopping = FakePhotoCraft(frozenset({"select.rect"}), stops=True)

    with pytest.raises(PhotoCraftError, match="answered 1 of a batch of 4 steps"):
        write_page(
            replace(access, addr=stopping.addr),
            work_of(bubble_comic),
            "001.png",
            bubble_items("Hi!"),
        )

    assert stopping.documents == []


def test_a_document_photocraft_cannot_activate_runs_no_step(photocraft: FakePhotoCraft) -> None:
    with connected(photocraft.addr, TOKEN) as session:
        document = Document(session, 7)
        with pytest.raises(PhotoCraftError, match="could not activate document 7: no document 7"):
            document.run_steps([BatchStep(command="select.deselect", params={})])


def test_a_write_waits_while_another_script_holds_photocraft(
    bubble_comic: Path, photocraft: FakePhotoCraft, access: PhotoCraftAccess
) -> None:
    work = work_of(bubble_comic)
    results: list[WriteResult] = []
    worker = threading.Thread(
        target=lambda: results.append(write_page(access, work, "001.png", bubble_items("Hi!")))
    )

    with held(access.lock):
        worker.start()
        time.sleep(0.5)
        assert photocraft.batches == []
    worker.join(timeout=30)

    assert [result.attempt for result in results] == [1]


def test_each_write_of_a_page_counts_one_more_attempt_and_keeps_its_items(
    bubble_comic: Path, access: PhotoCraftAccess
) -> None:
    work = work_of(bubble_comic)

    attempts = [
        write_page(access, work, "001.png", bubble_items(e)).attempt for e in ("Hi!", "Hey!")
    ]

    assert attempts == [1, 2]
    [entry] = work.translations().values()
    assert (entry.attempt, [item.english for item in entry.items]) == (2, ["Hey!"])


def test_a_page_with_no_items_keeps_its_original_as_english_and_still_checks_it(
    bubble_comic: Path, photocraft: FakePhotoCraft, access: PhotoCraftAccess
) -> None:
    work = work_of(bubble_comic)

    result = write_page(access, work, "001.png", [])

    english, original = Image.open(result.english), Image.open(work.page_file("001.png"))
    assert english.convert("RGB").tobytes() == original.convert("RGB").tobytes()
    assert result.attempt == 1
    assert photocraft.batches == []
    assert result.left_over != []


def test_a_rough_box_alone_in_its_bubble_clears_the_whole_bubble(
    bubble_comic: Path, access: PhotoCraftAccess
) -> None:
    rough = [Item(part=1, box_2d=ROUGH_BOX_2D, original="ABCDEFGHIJ", english="Hi!")]

    result = write_page(access, work_of(bubble_comic), "001.png", rough)

    assert result.left_over == []
