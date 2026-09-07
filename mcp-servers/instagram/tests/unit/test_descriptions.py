"""Prompt text is code, so it gets a test.

This is the mechanical half of that rule, and it exists because the harness's
TypeScript printer creates two specific failure modes that are invisible when you
read the source:

- `_one_line()` collapses a description with `" ".join(text.split())`, so any
  structure is discarded and a `*/` would end the comment early and leave the
  rest parsing as code.
- The printer emits argument types only and `RETURN_TYPE` is `Promise<unknown>`,
  so a field added to a return model but not to the prose is a field the model
  cannot know exists.
"""

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
    """`*/` inside the text would terminate the `/** ... */` the printer wraps it
    in, leaving the remainder to parse as TypeScript."""
    assert "*/" not in ALL[name]


@pytest.mark.parametrize(
    ("name", "model"),
    [("fetch_reels", FetchedReel), ("read_reels", ReadReel)],
)
def test_every_returned_field_is_named_in_the_prose(name: str, model: type) -> None:
    """The declaration says `Promise<unknown>`, so a field the prose does not
    mention is one the model has no way to discover."""
    text = ALL[name]
    missing = [field for field in model.model_fields if field not in text]

    assert missing == []


@pytest.mark.parametrize("name", sorted(ALL))
def test_a_description_names_its_own_arguments(name: str) -> None:
    """`Field(description=...)` on an argument model reaches nobody — the printer
    emits types without doc comments."""
    assert "args: {" in ALL[name]


def test_the_transcript_caveat_carries_the_observed_failure_not_a_generality() -> None:
    """A general "transcripts may be inaccurate" did not stop the model spelling a
    venue's name from audio. Two concrete misreadings did."""
    assert "Warung Maksik" in READ_DESCRIPTION
    assert "Jalan Tilikai" in READ_DESCRIPTION


def test_read_refuses_to_name_a_place_because_the_boundary_depends_on_it() -> None:
    """Without the sentence the vision model volunteers a venue and a confidence,
    and two models then disagree with no audit trail."""
    assert "never names a place" in READ_DESCRIPTION


def test_fetch_tells_the_model_to_batch_because_the_connection_is_sequential() -> None:
    """Nothing in the signature implies it, and a per-URL loop pays full latency
    per reel."""
    assert "ONE call" in FETCH_DESCRIPTION


def test_fetch_tells_the_model_not_to_abandon_a_batch_over_one_bad_item() -> None:
    """Observed: a model shown one `unavailable` item reports total failure."""
    assert "never fails the others" in FETCH_DESCRIPTION


@pytest.mark.parametrize("name", sorted(ALL))
def test_a_description_never_hardcodes_its_own_namespace(name: str) -> None:
    """The `{server}__{tool}` prefix the model sees comes from the *config key*,
    which this server cannot know. These descriptions said `igpoi__read_reels`
    until the server was re-keyed to `instagram`, at which point they would have
    told the model to call a function that does not exist. Bare names only."""
    assert "__" not in ALL[name]
