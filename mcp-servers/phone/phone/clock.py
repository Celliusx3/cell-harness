"""Time, injected."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Clock:
    now: Callable[[], float]
    sleep: Callable[[float], Awaitable[None]]


SYSTEM = Clock(now=time.monotonic, sleep=asyncio.sleep)
