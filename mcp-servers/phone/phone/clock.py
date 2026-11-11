"""Time, injected."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class Clock:
    now: Callable[[], float]
    sleep: Callable[[float], Awaitable[None]]
    wall: Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


SYSTEM = Clock(now=time.monotonic, sleep=asyncio.sleep, wall=utc_now)
