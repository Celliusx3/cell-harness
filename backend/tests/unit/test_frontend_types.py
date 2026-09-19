"""The frontend's wire types are kept in step with the backend's."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import get_args

import pytest

from harness.llm.messages import Block
from harness.llm.stream import StreamEvent
from harness.session.models import SessionEvent, TurnEndReason
from harness.skills.invocation import MARKER

_TYPES_TS = Path(__file__).resolve().parents[3] / "frontend" / "lib" / "types.ts"


@pytest.fixture(scope="module")
def types_ts() -> str:
    if not _TYPES_TS.exists():
        pytest.skip(f"{_TYPES_TS} is absent")
    return _TYPES_TS.read_text()


def _literal_of(model: type, field: str) -> str:
    """The single literal value pinned on a discriminator field."""
    annotation = model.model_fields[field].annotation
    return get_args(annotation)[0]


def test_every_session_event_type_is_declared(types_ts: str) -> None:
    missing = [
        _literal_of(member, "type")
        for member in get_args(SessionEvent)
        if f'type: "{_literal_of(member, "type")}"' not in types_ts
    ]

    assert missing == [], f"frontend/lib/types.ts is missing: {missing}"


def test_every_stream_chunk_kind_is_declared(types_ts: str) -> None:
    missing = [
        _literal_of(member, "kind")
        for member in get_args(StreamEvent)
        if f'kind: "{_literal_of(member, "kind")}"' not in types_ts
    ]

    assert missing == [], f"frontend/lib/types.ts is missing chunk kinds: {missing}"


def test_every_content_block_type_is_declared(types_ts: str) -> None:
    # `typing.Annotated` puts the union at arg 0.
    for block in get_args(get_args(Block)[0]):
        literal = _literal_of(block, "type")
        assert f'type: "{literal}"' in types_ts, f"types.ts does not declare block {literal!r}"


def test_every_turn_end_reason_is_declared(types_ts: str) -> None:
    declared = re.search(r"export type TurnEndReason =([^;]+);", types_ts)
    assert declared is not None, "TurnEndReason is not declared in types.ts"

    missing = [reason for reason in get_args(TurnEndReason) if f'"{reason}"' not in declared[1]]

    assert missing == [], f"frontend TurnEndReason is missing: {missing}"


def test_the_check_would_notice_an_absence(types_ts: str) -> None:
    assert 'type: "turn/start"' in types_ts
    assert 'type: "turn/invented"' not in types_ts


def test_the_invocation_marker_is_the_same_on_both_sides() -> None:
    source = (_TYPES_TS.parent / "invocation.ts").read_text()
    assert f"export const MARKER = {json.dumps(MARKER)};" in source
