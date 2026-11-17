"""The PC's start script, run on this machine against the real Xvfb."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("Xvfb") is None or shutil.which("xdpyinfo") is None,
    reason="needs Xvfb and xdpyinfo",
)

START = Path(__file__).parents[2] / "image" / "start"
DISPLAY = ":91"
LOCK = Path(f"/tmp/.X{DISPLAY[1:]}-lock")


def display_is_up() -> bool:
    probe = subprocess.run(["xdpyinfo", "-display", DISPLAY], capture_output=True, check=False)
    return probe.returncode == 0


@pytest.fixture
def lock_from_an_earlier_boot() -> Iterator[None]:
    LOCK.write_text(f"{os.getpid():>10}\n")
    yield
    LOCK.unlink(missing_ok=True)


def test_the_desktop_starts_over_a_lock_left_by_an_earlier_boot(
    lock_from_an_earlier_boot: None,
) -> None:
    start = subprocess.Popen(
        ["sh", str(START)],
        env={**os.environ, "DISPLAY": DISPLAY},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 10
        while not display_is_up() and time.monotonic() < deadline:
            time.sleep(0.2)
        assert display_is_up()
    finally:
        os.killpg(start.pid, signal.SIGTERM)
        start.wait()
