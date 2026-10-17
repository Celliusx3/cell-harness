"""Each chat's files on disk, under `<root>/<chat id>/<random folder>/`, readable by us alone."""

from __future__ import annotations

import secrets
import shutil
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

from harness.files.repository import is_plain_name

FOLDER_MODE = 0o700
TOKEN_BYTES = 16


@dataclass(frozen=True)
class DiskChatFileRepository:
    """Every chat's files, under `<root>/<chat id>/`."""

    root: Path

    def folder(self, chat_id: str) -> Path:
        """This chat's folder, resolved; `ValueError` for an id that is not one plain name."""
        if not is_plain_name(chat_id):
            raise ValueError(f"{chat_id!r} cannot name a chat's folder")
        return (self.root / chat_id).resolve()

    def path_in(self, chat_id: str, path: str) -> Path | None:
        """`path` resolved, when it is absolute and a file in this chat's folder; else `None`."""
        candidate = Path(path)
        if not candidate.is_absolute():
            return None
        try:
            resolved = candidate.resolve()
            inside = resolved.is_relative_to(self.folder(chat_id)) and resolved.is_file()
        except (OSError, ValueError):
            return None
        return resolved if inside else None

    async def write(self, chat_id: str, name: str, chunks: AsyncIterator[bytes]) -> Path:
        """`chunks` as the file `name` in a new folder of this chat's; on any failure none stays."""
        if not is_plain_name(name):
            raise ValueError(f"{name!r} cannot name a file")
        folder = self._create_upload_folder(chat_id)
        target = folder / name
        try:
            with target.open("xb") as handle:
                async for chunk in chunks:
                    handle.write(chunk)
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        return target

    def create_root(self) -> None:
        """The folder every chat's files live under, readable by us alone, made if missing."""
        self.root.mkdir(mode=FOLDER_MODE, parents=True, exist_ok=True)

    def _create_upload_folder(self, chat_id: str) -> Path:
        """A fresh folder under this chat's, named by a random token, readable by us alone."""
        self.create_root()
        chat = self.folder(chat_id)
        chat.mkdir(mode=FOLDER_MODE, exist_ok=True)
        fresh = chat / secrets.token_urlsafe(TOKEN_BYTES)
        fresh.mkdir(mode=FOLDER_MODE)
        return fresh
