"""The tool descriptions."""

from __future__ import annotations

import pytest

from places.models import Candidate, PlaceDetails
from places.tools.descriptions import DETAILS_DESCRIPTION, SEARCH_DESCRIPTION

ALL = {"search_text": SEARCH_DESCRIPTION, "place_details": DETAILS_DESCRIPTION}


@pytest.mark.parametrize("name", sorted(ALL))
def test_a_description_survives_being_collapsed_to_one_line(name: str) -> None:
    text = ALL[name]

    assert " ".join(text.split()) == text


@pytest.mark.parametrize("name", sorted(ALL))
def test_a_description_cannot_end_its_own_comment_block(name: str) -> None:
    assert "*/" not in ALL[name]


@pytest.mark.parametrize("name", sorted(ALL))
def test_a_description_names_its_arguments(name: str) -> None:
    assert "args: {" in ALL[name]


@pytest.mark.parametrize(
    ("name", "model"), [("search_text", Candidate), ("place_details", PlaceDetails)]
)
def test_every_returned_field_is_named_in_the_prose(name: str, model: type) -> None:
    missing = [field for field in model.model_fields if field not in ALL[name]]

    assert missing == []


def test_search_carries_the_concrete_example_of_a_query_that_fails() -> None:
    assert "blue awning" in SEARCH_DESCRIPTION
    assert "RE-RANK" in SEARCH_DESCRIPTION


def test_search_tells_the_model_it_cannot_save_to_a_list() -> None:
    assert "no API that can add a place to their saved list" in SEARCH_DESCRIPTION


def test_details_warns_that_it_is_a_more_expensive_tier() -> None:
    assert "more expensive billing tier" in DETAILS_DESCRIPTION
    assert "let them pick" in DETAILS_DESCRIPTION


@pytest.mark.parametrize("name", sorted(ALL))
def test_a_description_never_hardcodes_its_own_namespace(name: str) -> None:
    assert "__" not in ALL[name]
