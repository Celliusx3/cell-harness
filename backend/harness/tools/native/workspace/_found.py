"""What `workspace_search` hands back: one `path:line: text` per match, capped."""

from __future__ import annotations

from collections.abc import Sequence

from harness.files import Match
from harness.files.domain.search import SHOWN_MATCHES

SHOWN_LINE_CHARS = 300
CUT_MARK = "…"
NO_MATCH = "No text file in {folder} contains that text."
MORE_MATCHES = "More matches were left out. Search for a longer text to narrow them."


def _shown_line(line: str) -> str:
    """`line` up to `SHOWN_LINE_CHARS`, marked where it was cut."""
    if len(line) <= SHOWN_LINE_CHARS:
        return line
    return line[:SHOWN_LINE_CHARS] + CUT_MARK


def found(matches: Sequence[Match], folder: str) -> str:
    """The first `SHOWN_MATCHES` of `matches`, one per line, and whether there were more."""
    if not matches:
        return NO_MATCH.format(folder=folder)
    lines = [f"{m.path}:{m.number}: {_shown_line(m.line)}" for m in matches[:SHOWN_MATCHES]]
    if len(matches) > SHOWN_MATCHES:
        lines.append(MORE_MATCHES)
    return "\n".join(lines)
