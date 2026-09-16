"""Batching inbound text, and why it is timers.

Telegram's *client* splits a long paste into several messages, so without a
buffer one paste is several turns — a correctness bug, not a polish item, and
the reason Hermes buffers at all:

    "Buffer rapid text messages so Telegram client-side splits of long messages
     are aggregated into a single MessageEvent."

A hand-rolled poller could not use per-chat timers, because the poll loop then
had to decide what to acknowledge while dispatches were still pending. With PTB
holding the offset that coupling is gone, and the delays below are Hermes's.
"""

from __future__ import annotations

import asyncio

# Hermes's adaptive ingress delays, tuned for "feels instant". Short text reaches
# the model fast; only something long enough to have been client-split waits the
# full window.
FAST_LEN = 320
FAST_DELAY_SECONDS = 0.18
SHORT_LEN = 1024
SHORT_DELAY_SECONDS = 0.24
BATCH_DELAY_SECONDS = 0.30

# A message at or near the per-message limit was very likely cut by the client,
# so its continuation is worth waiting noticeably longer for.
SPLIT_SUSPECT_LEN = 4000
SPLIT_DELAY_SECONDS = 1.0

# What joins a batch: a newline, because that is how the lines were typed.
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
