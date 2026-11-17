"""The files a ready report names: in the chat's workspace, or out of the person's reach."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

ABSOLUTE_PATH = re.compile(r"(?<![\w:/.~-])/[^\s'\"`<>()\[\]{},;]+")
TRAILING_PUNCTUATION = ".,:;!?"


@dataclass(frozen=True)
class ReportedFiles:
    """The chat's files a report names by full path, and the other paths it names."""

    in_chat: tuple[str, ...]
    out_of_reach: tuple[str, ...]


def reported_files(summary: str, folder: str, chat_files: Sequence[str]) -> ReportedFiles:
    """Which of `chat_files` `summary` names, and which other absolute paths it names."""
    names_folder = folder in summary
    in_chat = tuple(
        path
        for path in chat_files
        if path in summary or (names_folder and _named_alone(path, folder, summary))
    )
    named = (
        found.group(0).rstrip(TRAILING_PUNCTUATION) for found in ABSOLUTE_PATH.finditer(summary)
    )
    out_of_reach = tuple(
        dict.fromkeys(path for path in named if not _is_part_of_the_chat(path, folder, in_chat))
    )
    return ReportedFiles(in_chat=in_chat, out_of_reach=out_of_reach)


def _named_alone(path: str, folder: str, summary: str) -> bool:
    """Whether `summary` names `path` by its name inside `folder` alone, as a list under the
    folder does, and not as part of a longer name."""
    name = path.removeprefix(folder).lstrip("/")
    return re.search(rf"(?<![\w./-]){re.escape(name)}(?![\w.-])", summary) is not None


def _is_part_of_the_chat(path: str, folder: str, in_chat: Sequence[str]) -> bool:
    """Whether `path` is in the chat's workspace, or the start of a path that is, cut at a space."""
    return path.startswith(folder) or any(full.startswith(path) for full in (folder, *in_chat))
