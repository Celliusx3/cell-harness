"""A workspace watched for changes on disk, one event per changed folder, until it is closed."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import suppress
from pathlib import Path

from watchfiles import awatch
from watchfiles.main import FileChange

from harness.files.domain.models import (
    WorkspaceChanged,
    WorkspaceEvent,
    WorkspaceWatching,
    changed_folders,
)

MOST_MS_BATCHED = 1_600
QUIET_MS_ENDING_A_BATCH = 50

Batches = AsyncGenerator[set[FileChange]]


def _with_real_folder(path: str) -> Path:
    """`path` with its folder's links followed, so a change through a link out lands outside."""
    changed = Path(path)
    return changed.parent.resolve() / changed.name


async def _started(batches: Batches) -> asyncio.Future[set[FileChange]]:
    """The first batch, waited on in a task that has set the watch up by the time this returns."""
    pending = asyncio.ensure_future(anext(batches))
    # awatch builds its watcher before its first await, so one step of the task sets it up.
    await asyncio.sleep(0)
    return pending


async def workspace_events(workspace: Path, stop: asyncio.Event) -> AsyncGenerator[WorkspaceEvent]:
    """`WorkspaceWatching` once `workspace` is watched, then each changed folder, until closed."""
    batches = awatch(
        workspace,
        recursive=True,
        stop_event=stop,
        watch_filter=None,
        debounce=MOST_MS_BATCHED,
        step=QUIET_MS_ENDING_A_BATCH,
    )
    pending = await _started(batches)
    try:
        yield WorkspaceWatching()
        while True:
            try:
                batch = await pending
            except StopAsyncIteration:
                return
            paths = (_with_real_folder(path) for _, path in batch)
            for folder in changed_folders(workspace, paths):
                yield WorkspaceChanged(folder=folder)
            pending = asyncio.ensure_future(anext(batches))
    finally:
        stop.set()
        with suppress(StopAsyncIteration, asyncio.CancelledError):
            await pending
        await batches.aclose()
