"""Batching inbound text with timers."""

from __future__ import annotations

import asyncio

FAST_LEN = 320
FAST_DELAY_SECONDS = 0.18
SHORT_LEN = 1024
SHORT_DELAY_SECONDS = 0.24
BATCH_DELAY_SECONDS = 0.30

SPLIT_SUSPECT_LEN = 4000
SPLIT_DELAY_SECONDS = 1.0

JOIN = "\n"


def batch_delay(text: str) -> float:
    """How long to wait for the rest of `text`, if more is coming."""
    if len(text) >= SPLIT_SUSPECT_LEN:
        return SPLIT_DELAY_SECONDS
    if len(text) <= FAST_LEN:
        return FAST_DELAY_SECONDS
    if len(text) <= SHORT_LEN:
        return SHORT_DELAY_SECONDS
    return BATCH_DELAY_SECONDS


class Batch:
    """Text accumulating for one chat, and the timer that will dispatch it."""

    __slots__ = ("text", "timer")

    def __init__(self, text: str, timer: asyncio.Task[None]) -> None:
        self.text = text
        self.timer = timer
