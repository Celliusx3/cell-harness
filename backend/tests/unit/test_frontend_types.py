"""The frontend's wire types are kept in step with the backend's.

`frontend/lib/types.ts` is hand-written — a generator would be a build step and a
toolchain for nine small types. The trade is that it can silently fall behind, so
this is the check that makes falling behind loud.

It is deliberately a *Python* test. Adding an event type is a backend change, and
the failure has to land in the suite that change runs — not in a `npm run
typecheck` nobody invokes while editing `models.py`.

This is the project's "two things stay in step" practice, the same shape as
cell-bot's templates-versus-enum test.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import get_args

import pytest

from harness.llm.stream import StreamEvent
from harness.session.models import SessionEvent, TurnEndReason

_TYPES_TS = Path(__file__).resolve().parents[3] / "frontend" / "lib" / "types.ts"


@pytest.fixture(scope="module")
def types_ts() -> str:
    if not _TYPES_TS.exists():  # pragma: no cover - only if the frontend is removed
        pytest.skip(f"{_TYPES_TS} is absent")
    return _TYPES_TS.read_text()


def _literal_of(model: type, field: str) -> str:
    """The single literal value pinned on a discriminator field."""
    annotation = model.model_fields[field].annotation
    return get_args(annotation)[0]


def test_every_session_event_type_is_declared(types_ts: str) -> None:
    """A new event type with no renderer fails here, not in the browser."""
    missing = [
        _literal_of(member, "type")
        for member in get_args(SessionEvent)
        if f'type: "{_literal_of(member, "type")}"' not in types_ts
    ]

    assert missing == [], f"frontend/lib/types.ts is missing: {missing}"


def test_every_stream_chunk_kind_is_declared(types_ts: str) -> None:
    """`assistant/chunk` carries this union, so the reducer has to know it all.

    Notably `completed`: it holds `full_text`, and a reducer that treats every
    chunk as text to append renders the whole reply twice.
    """
    missing = [
        _literal_of(member, "kind")
        for member in get_args(StreamEvent)
        if f'kind: "{_literal_of(member, "kind")}"' not in types_ts
    ]

    assert missing == [], f"frontend/lib/types.ts is missing chunk kinds: {missing}"


def test_every_turn_end_reason_is_declared(types_ts: str) -> None:
    """The UI branches on these — a new one must not fall through silently."""
    declared = re.search(r"export type TurnEndReason =([^;]+);", types_ts)
    assert declared is not None, "TurnEndReason is not declared in types.ts"

    missing = [reason for reason in get_args(TurnEndReason) if f'"{reason}"' not in declared[1]]

    assert missing == [], f"frontend TurnEndReason is missing: {missing}"


def test_the_check_would_notice_an_absence(types_ts: str) -> None:
    """The guard's own guard.

    A matcher that never fails is worse than no matcher, and the substring search
    above is exactly the kind that quietly matches everything if the format
    assumption is wrong.
    """
    assert 'type: "turn/start"' in types_ts
    assert 'type: "turn/invented"' not in types_ts
