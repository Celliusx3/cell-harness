"""`tickets.json`, read whole and replaced whole."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from harness.tickets.models import TicketsFile


class TicketRepository:
    """One file holding every ticket; a missing file holds none."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def read(self) -> TicketsFile:
        """What the file holds right now."""
        if not self._path.exists():
            return TicketsFile()
        return TicketsFile.model_validate_json(self._path.read_text(encoding="utf-8"))

    def write(self, stored: TicketsFile) -> None:
        """Replace the file with `stored`, so a reader never sees half of it."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            file.write(stored.model_dump_json(indent=2))
        os.replace(temp, self._path)
