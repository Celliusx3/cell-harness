"""`bots.json`, read whole and replaced whole."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from harness.bots.domain.models import BotsFile


class BotRepository:
    """One file holding every made bot and every group; a missing file holds none."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def read(self) -> BotsFile:
        """What the file holds right now."""
        if not self._path.exists():
            return BotsFile()
        return BotsFile.model_validate_json(self._path.read_text(encoding="utf-8"))

    def write(self, stored: BotsFile) -> None:
        """Replace the file with `stored`, so a reader never sees half of it."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            file.write(stored.model_dump_json(indent=2))
        os.replace(temp, self._path)
