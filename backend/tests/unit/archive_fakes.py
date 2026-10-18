"""Archives drawn in the test: tiny PNG pages zipped under any entry name, in a chat's folder."""

from __future__ import annotations

import json
import stat
import struct
import zipfile
import zlib
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple

from harness.files import DiskChatFileRepository
from tests.unit.helpers import CONVERSATION_ID

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
UNPACK_LIMIT = 1024 * 1024


class Entry(NamedTuple):
    name: str
    body: bytes


def png_chunk(kind: bytes, body: bytes) -> bytes:
    crc = zlib.crc32(kind + body)
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", crc)


def drawn_png(shade: int) -> bytes:
    """A one-pixel grey PNG of `shade`."""
    header = struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0)
    pixels = zlib.compress(bytes([0, shade]))
    return (
        PNG_SIGNATURE
        + png_chunk(b"IHDR", header)
        + png_chunk(b"IDAT", pixels)
        + png_chunk(b"IEND", b"")
    )


def chat_folder(tmp_path: Path) -> Path:
    """An upload folder among the files of the conversation the tests call from."""
    folder = DiskChatFileRepository(tmp_path / "files").folder(CONVERSATION_ID) / "upload"
    folder.mkdir(parents=True)
    return folder


def zipped(path: Path, entries: Sequence[Entry]) -> Path:
    """`entries` written into a new zip at `path`, in the order given, stored as is."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as archive:
        for entry in entries:
            archive.writestr(entry.name, entry.body)
    return path


def link_entry(name: str) -> zipfile.ZipInfo:
    """An entry a Unix zip marks as a symbolic link; the body written with it is its target."""
    info = zipfile.ZipInfo(name)
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    return info


def every_file_under(folder: Path) -> set[Path]:
    return {path for path in folder.rglob("*") if path.is_file()}


def extracting(path: str) -> str:
    return json.dumps({"path": path})


def making(paths: Sequence[str], name: str) -> str:
    return json.dumps({"paths": list(paths), "name": name})
