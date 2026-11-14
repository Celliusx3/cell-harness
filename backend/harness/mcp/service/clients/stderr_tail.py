"""A server's stderr passed on to the app's own, with its last lines kept to explain a failure."""

from __future__ import annotations

import os
import threading
from collections import deque
from dataclasses import dataclass
from typing import TextIO

KEPT_LINE_COUNT = 20
DRAIN_SECONDS = 2.0


@dataclass(frozen=True)
class StderrTail:
    """The file a server writes its stderr to, and the lines kept from it."""

    writer: TextIO
    lines: deque[str]
    pump: threading.Thread

    def drain_last_line(self) -> str:
        """The server's last non-blank line, once its output is drained; empty if it wrote none."""
        self.writer.close()
        self.pump.join(DRAIN_SECONDS)
        return next((line for line in reversed(self.lines) if line.strip()), "")


def tee_stderr(sink: TextIO) -> StderrTail:
    """A pipe whose every line goes on to `sink`, the last KEPT_LINE_COUNT of them kept."""
    read_fd, write_fd = os.pipe()
    lines: deque[str] = deque(maxlen=KEPT_LINE_COUNT)

    def pass_on() -> None:
        with os.fdopen(read_fd, encoding="utf-8", errors="replace") as reader:
            for line in reader:
                sink.write(line)
                sink.flush()
                lines.append(line.rstrip("\n"))

    pump = threading.Thread(target=pass_on, name="mcp-stderr", daemon=True)
    pump.start()
    return StderrTail(writer=os.fdopen(write_fd, "w"), lines=lines, pump=pump)
