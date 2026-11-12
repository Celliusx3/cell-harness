"""Each bot's places for running worker turns: its limit, one extra for an answer, a line."""

from __future__ import annotations

import asyncio
import dataclasses
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Literal

PlaceKind = Literal["normal", "extra"]


@dataclass(frozen=True)
class Occupancy:
    """One bot's places in use: how many normal ones, and whether its extra one is."""

    running: int = 0
    extra_in_use: bool = False


def place_for(
    held: Occupancy, limit: int, *, first_in_line: bool, answer: bool
) -> PlaceKind | None:
    """The place a turn may take now, or `None` to wait; an answer skips the line."""
    if (first_in_line or answer) and held.running < limit:
        return "normal"
    if answer and not held.extra_in_use:
        return "extra"
    return None


def taken(held: Occupancy, kind: PlaceKind) -> Occupancy:
    """`held` with one more place of `kind` in use."""
    if kind == "extra":
        return dataclasses.replace(held, extra_in_use=True)
    return dataclasses.replace(held, running=held.running + 1)


def freed(held: Occupancy, kind: PlaceKind) -> Occupancy:
    """`held` with one place of `kind` given back."""
    if kind == "extra":
        return dataclasses.replace(held, extra_in_use=False)
    return dataclasses.replace(held, running=held.running - 1)


class Places:
    """Gives each bot's turns their places, in the order asked, reading its limit every time."""

    def __init__(self, limit_of: Callable[[str], int]) -> None:
        self._limit_of = limit_of
        self._held: dict[str, Occupancy] = {}
        self._lines: dict[str, tuple[object, ...]] = {}
        self._changed = asyncio.Condition()

    @asynccontextmanager
    async def place(
        self, bot_id: str, *, answer: bool, on_wait: Callable[[], None]
    ) -> AsyncIterator[None]:
        """Hold a place for `bot_id` while inside; `on_wait` is called once if it must wait."""
        kind = await self._take(bot_id, answer=answer, on_wait=on_wait)
        try:
            yield
        finally:
            async with self._changed:
                self._held[bot_id] = freed(self._held[bot_id], kind)
                self._changed.notify_all()

    async def _take(self, bot_id: str, *, answer: bool, on_wait: Callable[[], None]) -> PlaceKind:
        token = object()
        if not answer:
            self._lines[bot_id] = (*self._lines.get(bot_id, ()), token)
        async with self._changed:
            try:
                kind = self._grant(bot_id, token, answer)
                if kind is None:
                    on_wait()
                while kind is None:
                    await self._changed.wait()
                    kind = self._grant(bot_id, token, answer)
            finally:
                self._lines[bot_id] = tuple(
                    t for t in self._lines.get(bot_id, ()) if t is not token
                )
                self._changed.notify_all()
            self._held[bot_id] = taken(self._held.get(bot_id, Occupancy()), kind)
            return kind

    def _grant(self, bot_id: str, token: object, answer: bool) -> PlaceKind | None:
        line = self._lines.get(bot_id, ())
        first = bool(line) and line[0] is token
        held = self._held.get(bot_id, Occupancy())
        return place_for(held, self._limit_of(bot_id), first_in_line=first, answer=answer)
