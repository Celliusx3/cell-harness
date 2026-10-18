"""Image bytes on disk, at `<root>/<sha256>.<ext>`, each written once and readable by us alone."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from harness.images.models import ImageFile

BLOBS = "blobs"
FOLDER_MODE = 0o700
_EXTENSIONS: Mapping[str, str] = MappingProxyType(
    {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif"}
)


@dataclass(frozen=True)
class DiskImageRepository:
    """Image bytes at `<root>/<sha256>.<ext>`, each written once and never rewritten."""

    root: Path

    def write(self, sha256: str, media_type: str, data: bytes) -> None:
        """`data` kept under `sha256` unless a file already is, whole or not at all."""
        target = self._path_of(sha256, media_type)
        if not target.exists():
            self._write_whole(target, data)

    def read(self, sha256: str, media_type: str) -> bytes:
        """The bytes kept under `sha256`; `OSError` when there are none."""
        return self._path_of(sha256, media_type).read_bytes()

    def file_of(self, sha256: str) -> ImageFile | None:
        """The kept file named `sha256`, whatever its extension; `None` when there is none."""
        for media_type, extension in _EXTENSIONS.items():
            path = self.root / f"{sha256}.{extension}"
            if path.is_file():
                return ImageFile(path=path, media_type=media_type)
        return None

    def _path_of(self, sha256: str, media_type: str) -> Path:
        """Where the image named `sha256` is kept as `media_type`."""
        return self.root / f"{sha256}.{_EXTENSIONS[media_type]}"

    def _write_whole(self, target: Path, data: bytes) -> None:
        """Write `data` whole to `target` or not at all, in a folder only we can read."""
        self.root.mkdir(mode=FOLDER_MODE, parents=True, exist_ok=True)
        handle, partial = tempfile.mkstemp(dir=self.root, prefix=".", suffix=".part")
        try:
            with os.fdopen(handle, "wb") as file:
                file.write(data)
            os.replace(partial, target)
        except BaseException:
            Path(partial).unlink(missing_ok=True)
            raise
