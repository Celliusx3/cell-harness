"""A page PhotoCraft saves on the Mac is read only once the computer sees the new file whole."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from PIL import Image

from comic import ComicError, document
from comic.document import Document

LANDS_AFTER_SECONDS = 0.3


class LateSave:
    """A session whose `doc.save` lands on disk a moment after it answers, as over a mount."""

    def __init__(self, colour: str | None) -> None:
        self.colour = colour

    def request(self, method: str, params: dict) -> dict:
        assert method == "doc.save"
        path = Path(params["path"])
        if self.colour is not None:
            colour = self.colour
            threading.Timer(
                LANDS_AFTER_SECONDS, lambda: Image.new("RGB", (4, 4), colour).save(path)
            ).start()
        return {"path": str(path), "warnings": []}


def test_a_save_that_lands_late_is_waited_for(tmp_path: Path) -> None:
    page = tmp_path / "clean.png"

    Document(session=LateSave("white"), index=0).save(page)

    assert Image.open(page).getpixel((0, 0)) == (255, 255, 255)


def test_the_old_page_is_never_read_back_as_the_new_one(tmp_path: Path) -> None:
    page = tmp_path / "clean.png"
    Image.new("RGB", (4, 4), "black").save(page)

    Document(session=LateSave("white"), index=0).save(page)

    assert Image.open(page).getpixel((0, 0)) == (255, 255, 255)


def test_a_save_that_never_lands_is_refused_in_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(document, "SAVE_SETTLE_SECONDS", 0.5)

    with pytest.raises(ComicError, match="did not appear"):
        Document(session=LateSave(None), index=0).save(tmp_path / "clean.png")
