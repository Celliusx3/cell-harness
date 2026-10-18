"""The lock that lets one script at a time work inside PhotoCraft."""

from __future__ import annotations

import fcntl
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def held(path: Path) -> Iterator[None]:
    """An exclusive `flock` on `path`, created if missing, held until the block exits."""
    with path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield
