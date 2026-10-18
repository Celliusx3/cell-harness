"""Only one script at a time works inside PhotoCraft."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from comic.lock import held


@contextmanager
def holding(lock: Path, log: list[str], name: str, seconds: float) -> Iterator[None]:
    with held(lock):
        log.append(f"{name} in")
        time.sleep(seconds)
        log.append(f"{name} out")
        yield


def test_a_second_holder_of_the_lock_waits_for_the_first(tmp_path: Path) -> None:
    lock, log = tmp_path / "photocraft.lock", []

    def first() -> None:
        with holding(lock, log, "first", 0.3):
            pass

    worker = threading.Thread(target=first)
    worker.start()
    time.sleep(0.05)
    with holding(lock, log, "second", 0):
        pass
    worker.join()

    assert log == ["first in", "first out", "second in", "second out"]
