"""Each item becomes where its text is on the page, what to clear and the sizes to try."""

from __future__ import annotations

import pytest

from comic import ComicError
from comic.chapter.pages import Box, Item, Page, Size
from comic.chapter.parts import part_areas
from comic.chapter.plan import Plan, plans_of, text_box

TALL_PAGE = Page(page="001.png", size=Size(1000, 6000), parts=part_areas(Size(1000, 6000)))
SMALL_PAGE = Page(page="002.png", size=Size(200, 300), parts=part_areas(Size(200, 300)))


def test_a_box_2d_is_read_in_thousandths_of_its_part() -> None:
    hello = Item(part=2, box_2d=(100, 200, 300, 600), original="안녕", english="Hello")

    assert TALL_PAGE.parts[1] == Box(0, 2000, 1000, 2500)
    assert text_box(TALL_PAGE, hello) == Box(200, 2250, 400, 500)


def test_an_item_is_planned_with_sizes_from_the_page_width() -> None:
    [plan] = plans_of(
        TALL_PAGE, [Item(part=2, box_2d=(100, 200, 300, 600), original="안녕", english="Hello")]
    )

    assert plan == Plan(
        english="Hello",
        text=Box(200, 2250, 400, 500),
        erase=Box(192, 2242, 416, 516),
        fill=Box(175, 2225, 450, 550),
        px=50,
        smallest=20,
    )


def test_a_box_at_the_corner_is_padded_only_onto_the_page_and_no_smaller_than_12_px() -> None:
    [plan] = plans_of(
        SMALL_PAGE, [Item(part=1, box_2d=(0, 0, 100, 100), original="안녕", english="Hi")]
    )

    assert plan.text == Box(0, 0, 20, 30)
    assert plan.erase == Box(0, 0, 28, 38)
    assert plan.fill == Box(0, 0, 26, 36)
    assert (plan.px, plan.smallest) == (12, 12)


@pytest.mark.parametrize("part", [0, 4])
def test_an_item_naming_a_part_the_page_lacks_is_refused_by_its_english(part: int) -> None:
    lost = Item(part=part, box_2d=(100, 100, 200, 200), original="안녕", english="Where?")

    with pytest.raises(ComicError, match=f"'Where\\?' names part {part}, .* parts 1 to 3"):
        plans_of(TALL_PAGE, [lost])


def test_one_bubble_sent_from_two_parts_is_refused_naming_both() -> None:
    above = Item(part=1, box_2d=(850, 100, 950, 400), original="안녕", english="Run!")
    below = Item(part=2, box_2d=(50, 100, 150, 400), original="안녕", english="Run, now!")

    with pytest.raises(ComicError) as refused:
        plans_of(TALL_PAGE, [above, below])

    assert "'Run!' (part 1) and 'Run, now!' (part 2) are the same bubble" in str(refused.value)
    assert "send that bubble once, from the part that shows all of it" in str(refused.value)


def test_two_bubbles_that_barely_touch_are_both_planned() -> None:
    left = Item(part=1, box_2d=(100, 100, 200, 400), original="안녕", english="One")
    right = Item(part=1, box_2d=(100, 350, 200, 700), original="안녕", english="Two")

    assert [plan.english for plan in plans_of(TALL_PAGE, [left, right])] == ["One", "Two"]
