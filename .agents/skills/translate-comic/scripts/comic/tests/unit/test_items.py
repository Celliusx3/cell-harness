"""An item names a part, a box_2d of four thousandths in order, its original text and English."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from comic.chapter.pages import Item


def item(box_2d: list[int], english: str = "Hello", original: str = "안녕") -> Item:
    return Item.model_validate(
        {"part": 1, "box_2d": box_2d, "original": original, "english": english}
    )


def test_an_item_as_the_model_sends_it_is_read() -> None:
    assert item([100, 200, 300, 400]).box_2d == (100, 200, 300, 400)


@pytest.mark.parametrize("box_2d", [[0, 0, 1001, 10], [-1, 0, 10, 10]])
def test_a_box_2d_outside_0_to_1000_is_refused(box_2d: list[int]) -> None:
    with pytest.raises(ValidationError, match="box_2d"):
        item(box_2d)


@pytest.mark.parametrize("box_2d", [[300, 200, 100, 400], [100, 400, 300, 400]])
def test_an_inverted_box_2d_is_refused_naming_the_item(box_2d: list[int]) -> None:
    with pytest.raises(ValidationError, match="'Hello' has box_2d .*ymin must be under ymax"):
        item(box_2d)


@pytest.mark.parametrize("box_2d", [[1, 2, 3], [1, 2, 3, 4, 5]])
def test_a_box_2d_of_other_than_four_numbers_is_refused(box_2d: list[int]) -> None:
    with pytest.raises(ValidationError, match="box_2d"):
        item(box_2d)


def test_an_item_with_no_english_is_refused() -> None:
    with pytest.raises(ValidationError, match="english"):
        item([100, 200, 300, 400], english="")


def test_an_item_keeps_its_original_text() -> None:
    assert item([100, 200, 300, 400], original="こんにちは").original == "こんにちは"


def test_an_item_with_an_empty_original_is_refused() -> None:
    with pytest.raises(ValidationError, match="original"):
        item([100, 200, 300, 400], original="")


def test_an_item_without_its_original_is_refused() -> None:
    with pytest.raises(ValidationError, match="original"):
        Item.model_validate({"part": 1, "box_2d": [100, 200, 300, 400], "english": "Hello"})
