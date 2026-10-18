"""SKILL.md keeps the ledger's sentences, and names every field the bot reads."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from comic.models import ListedPage, PagesResult, WriteResult

SKILL = Path(__file__).parents[4] / "SKILL.md"


@pytest.mark.parametrize(
    "sentence",
    [
        "Each write replaces the page's English and starts again from the original page, "
        "so send all of the page's items every time, also when you fix one box or one line.",
        "cover every letter and stay inside the bubble's outline.",
        "Two bubbles that touch are two items.",
        "`original` is that text exactly as you read it in the image.",
        "Each area in `left_over` still holds text, given as `part` and `box_2d` like an "
        "item's: when it is a bubble or caption, add an item for it or widen the box of the "
        "item that only partly covered it; when it is part of the drawing, leave it.",
        "Stop fixing the page when the checks are clear or its `attempt` is 3.",
    ],
)
def test_a_sentence_that_fixed_a_model_failure_is_still_in_the_skill(sentence: str) -> None:
    assert sentence in " ".join(SKILL.read_text().split())


@pytest.mark.parametrize("result", [PagesResult, ListedPage, WriteResult])
def test_every_field_a_result_the_bot_acts_on_prints_is_named_in_the_skill(
    result: type[BaseModel],
) -> None:
    text = SKILL.read_text()
    assert [field for field in result.model_fields if f"`{field}`" not in text] == []
