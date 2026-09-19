"""The tool descriptions."""

from __future__ import annotations

import pytest

from instagram.models import FetchedReel, ReadReel
from instagram.tools.descriptions import FETCH_DESCRIPTION, READ_DESCRIPTION

ALL = {"fetch_reels": FETCH_DESCRIPTION, "read_reels": READ_DESCRIPTION}


@pytest.mark.parametrize("name", sorted(ALL))
def test_a_description_survives_the_harness_collapsing_it_to_one_line(name: str) -> None:
    text = ALL[name]

    assert " ".join(text.split()) == text, "already one line, so the printer changes nothing"


@pytest.mark.parametrize("name", sorted(ALL))
def test_a_description_cannot_end_its_own_comment_block(name: str) -> None:
    assert "*/" not in ALL[name]


@pytest.mark.parametrize(
    ("name", "model"),
    [("fetch_reels", FetchedReel), ("read_reels", ReadReel)],
)
def test_every_returned_field_is_named_in_the_prose(name: str, model: type) -> None:
    text = ALL[name]
    missing = [field for field in model.model_fields if field not in text]

    assert missing == []


@pytest.mark.parametrize("name", sorted(ALL))
def test_a_description_names_its_own_arguments(name: str) -> None:
    assert "args: {" in ALL[name]


def test_the_transcript_caveat_carries_the_observed_failure_not_a_generality() -> None:
    assert "Warung Maksik" in READ_DESCRIPTION
    assert "Jalan Tilikai" in READ_DESCRIPTION


def test_read_refuses_to_name_a_place_because_the_boundary_depends_on_it() -> None:
    assert "never names a place" in READ_DESCRIPTION


def test_fetch_tells_the_model_to_batch_because_the_connection_is_sequential() -> None:
    assert "ONE call" in FETCH_DESCRIPTION


def test_fetch_tells_the_model_not_to_abandon_a_batch_over_one_bad_item() -> None:
    assert "never fails the others" in FETCH_DESCRIPTION


@pytest.mark.parametrize("name", sorted(ALL))
def test_a_description_never_hardcodes_its_own_namespace(name: str) -> None:
    assert "__" not in ALL[name]
