"""The saved servers on disk: one JSON file, beside the bots file."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from harness.mcp.models.saved import SavedServer, SavedServersFile


@dataclass(frozen=True)
class DiskSavedServerRepository:
    """The saved servers as one file at `path`, replaced whole."""

    path: Path

    def saved_servers(self) -> tuple[SavedServer, ...]:
        """Every saved server; `()` when there is no file."""
        if not self.path.exists():
            return ()
        return SavedServersFile.model_validate_json(self.path.read_text(encoding="utf-8")).servers

    def replace_all(self, servers: tuple[SavedServer, ...]) -> None:
        """The file replaced whole by `servers`, its folder made when missing."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            file.write(SavedServersFile(servers=servers).model_dump_json(indent=2))
        os.replace(temp, self.path)
