"""Finding a text in a workspace's files: every line that holds it, ignoring case."""

from __future__ import annotations

from collections.abc import Iterable
from itertools import islice
from typing import NamedTuple

SHOWN_MATCHES = 100


class TextFile(NamedTuple):
    """One UTF-8 text file of a workspace: its path, and its text."""

    path: str
    text: str


class Match(NamedTuple):
    """One line that holds the text searched for, numbered from 1, as it is in the file."""

    path: str
    number: int
    line: str


def matches(files: Iterable[TextFile], query: str) -> tuple[Match, ...]:
    """The lines of `files` holding `query`, ignoring case, in order, one past `SHOWN_MATCHES`."""
    folded = query.casefold()
    found = (
        Match(path=file.path, number=number, line=line)
        for file in files
        for number, line in enumerate(file.text.splitlines(), start=1)
        if folded in line.casefold()
    )
    return tuple(islice(found, SHOWN_MATCHES + 1))
