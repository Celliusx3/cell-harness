"""The paths a file tool is given, resolved only when each names a file in the calling chat."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from harness.files import ChatFileService
from harness.tools.models.outcome import INVALID_ARGUMENTS, Failure


def paths_in_chat(
    files: ChatFileService, conversation_id: str, paths: Sequence[str]
) -> tuple[Path, ...] | Failure:
    """Each of `paths` resolved, in order; a `Failure` naming the first not in this chat."""
    found: list[Path] = []
    for path in paths:
        stored = files.file_at(conversation_id, path)
        if stored is None:
            return Failure(INVALID_ARGUMENTS, f"{path} is not a file in this chat")
        found.append(Path(stored.path))
    return tuple(found)
