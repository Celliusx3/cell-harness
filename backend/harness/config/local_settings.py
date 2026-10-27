"""The per-machine settings file a saved key goes into: merged by path, written owner-only."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path

from pydantic import JsonValue

OWNER_ONLY_MODE = 0o600


def with_values(
    contents: dict[str, JsonValue], values: Mapping[str, str | None]
) -> dict[str, JsonValue]:
    """The contents with each `section.name` set, or removed when its value is None."""
    merged = {
        key: dict(value) if isinstance(value, dict) else value for key, value in contents.items()
    }
    for path, value in values.items():
        section, name = path.split(".", 1)
        current = merged.get(section)
        entries = dict(current) if isinstance(current, dict) else {}
        if value is None:
            entries.pop(name, None)
        else:
            entries[name] = value
        merged[section] = entries
    return merged


def read_local_settings(path: Path) -> dict[str, JsonValue]:
    """The file's contents, or nothing when there is no file yet; a file that is not JSON raises."""
    if not path.exists():
        return {}
    loaded = json.loads(path.read_text())
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} does not hold a JSON object")
    return loaded


def write_local_settings(path: Path, contents: dict[str, JsonValue]) -> None:
    """Replaces the file in one rename, readable by its owner only."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w") as handle:
            json.dump(contents, handle, indent=2)
            handle.write("\n")
        os.chmod(temp, OWNER_ONLY_MODE)
        os.replace(temp, path)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise
