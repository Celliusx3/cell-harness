"""Each worker's log sits beside the conversations, never among them."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.config import Settings
from harness.session.domain.models import TurnStart
from harness.session.repository.session_repository import SessionNotFoundError
from harness.web.server import build_sessions, build_subagent_logs


async def test_worker_logs_sit_beside_the_conversations_and_are_not_among_them(
    tmp_path: Path,
) -> None:
    settings = Settings(sessions={"root": tmp_path / "sessions"})
    logs = build_subagent_logs(settings)
    log = await logs.create("ticket-t1")
    log.append(TurnStart(turn=0))
    await logs.flush(log)

    assert (tmp_path / "subagents" / "ticket-t1.jsonl").exists()
    with pytest.raises(SessionNotFoundError):
        await build_sessions(settings).read("ticket-t1")
