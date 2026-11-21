"""The speaker's memory, and its group's in a group's chat, read from disk on every request."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from harness.files import WorkspaceFileError, WorkspaceTextService
from harness.files.domain.memory_view import (
    GROUP_WORDING,
    MEMORY_PATH,
    OWN_WORDING,
    Wording,
    memory_view,
)
from harness.runtime.hooks.service import StepHook
from harness.session.domain.models import WorkspaceEvent


@dataclass(frozen=True)
class WorkspaceMemoryHook(StepHook):
    """Each told workspace's `MEMORY_PATH`, its own first, read from disk every step."""

    texts: WorkspaceTextService

    async def start_of_step(self, named: WorkspaceEvent | None) -> str | None:
        if named is None:
            return None
        if named.own_workspace is None:
            return await self._part(Path(named.workspace), OWN_WORDING)
        own = await self._part(Path(named.own_workspace), OWN_WORDING)
        group = await self._part(Path(named.workspace), GROUP_WORDING)
        return "\n\n".join(part for part in (own, group) if part is not None) or None

    async def _part(self, workspace: Path, wording: Wording) -> str | None:
        """One workspace's memory, or that it has none; `None` when it cannot be read."""
        try:
            memory = await self.texts.memory(workspace)
        except WorkspaceFileError:
            return None
        return memory_view(str(workspace / MEMORY_PATH), memory, wording)
