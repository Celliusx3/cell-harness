"""A watched workspace on disk: made when missing, links out not told, stopped on close."""

from __future__ import annotations

import asyncio

from harness.files.domain.models import WorkspaceChanged, WorkspaceWatching
from harness.files.service.workspace_watch import workspace_events
from tests.integration.test_web_stream import TIMEOUT
from tests.webapp import files_in


async def test_closing_the_events_stops_the_watch_and_leaves_no_task(tmp_path) -> None:
    stop = asyncio.Event()
    events = workspace_events(tmp_path, stop)

    first = await anext(events)
    await events.aclose()

    assert first == WorkspaceWatching()
    assert stop.is_set()
    assert asyncio.all_tasks() == {asyncio.current_task()}


async def test_a_chat_with_no_workspace_has_one_made_once_watched(tmp_path) -> None:
    files = files_in(tmp_path)
    workspace = files.workspace("bot-1").parent / "bot-2"

    events = files.changes("bot-2")
    first = await anext(events)
    await events.aclose()

    assert first == WorkspaceWatching()
    assert workspace.is_dir()


async def test_a_change_through_a_folder_link_out_of_the_workspace_is_not_told(tmp_path) -> None:
    workspace, outside = tmp_path.resolve() / "workspace", tmp_path.resolve() / "outside"
    workspace.mkdir()
    outside.mkdir()
    (workspace / "away").symlink_to(outside)
    events = workspace_events(workspace, asyncio.Event())

    await anext(events)
    (workspace / "away" / "secret.txt").write_bytes(b"x")
    (workspace / "seen.txt").write_bytes(b"x")
    told = await asyncio.wait_for(anext(events), timeout=TIMEOUT)
    await events.aclose()

    assert told == WorkspaceChanged(folder="")
