"""The home folder's files, listed, read and written by Python run in the computer (see NOTICE)."""

from __future__ import annotations

import base64
import binascii
import logging
from collections.abc import Sequence

from pydantic import TypeAdapter, ValidationError

from computer.docker import COMMAND_TIMEOUT_SECONDS, CommandResult, Docker
from computer.machine import HOME
from computer.models import (
    TRANSFER_LIMIT_BYTES,
    FileBytes,
    FileEntry,
    FileText,
    HomePath,
    Listing,
    Uploaded,
)

logger = logging.getLogger("computer")

MIB = 1024 * 1024
READ_LIMIT_BYTES = 2 * MIB
TOO_LARGE_EXIT_CODE = 42
ENTRIES: TypeAdapter[list[FileEntry]] = TypeAdapter(list[FileEntry])

LIST_SCRIPT = "\n".join(
    [
        "import json, os, sys",
        "home, root, rel = sys.argv[1], sys.argv[2], sys.argv[3]",
        "real, home = os.path.realpath(root), os.path.realpath(home)",
        "if real != home and not real.startswith(home + os.sep):",
        "    sys.exit('the path leads outside the home folder')",
        "try:",
        "    items = list(os.scandir(root))",
        "except OSError as err:",
        "    sys.exit(str(err))",
        "out = []",
        "for item in items:",
        "    if item.is_symlink():",
        "        continue",
        "    info = item.stat(follow_symlinks=False)",
        "    kind = 'dir' if item.is_dir(follow_symlinks=False) else 'file'",
        "    child = '/'.join(x for x in (rel, item.name) if x)",
        "    out.append({'path': child, 'kind': kind, 'size': info.st_size})",
        "print(json.dumps(sorted(out, key=lambda x: x['path'])))",
    ]
)

READ_SCRIPT = "\n".join(
    [
        "import base64, os, sys",
        "home, target, limit = sys.argv[1], sys.argv[2], int(sys.argv[3])",
        "real, home = os.path.realpath(target), os.path.realpath(home)",
        "if real != home and not real.startswith(home + os.sep):",
        "    sys.exit('the path leads outside the home folder')",
        "try:",
        "    with open(target, 'rb') as source:",
        "        content = source.read(limit + 1)",
        "except OSError as err:",
        "    sys.exit(str(err))",
        f"if len(content) > limit: sys.exit({TOO_LARGE_EXIT_CODE})",
        "sys.stdout.write(base64.b64encode(content).decode())",
    ]
)

WRITE_SCRIPT = "\n".join(
    [
        "import base64, os, sys",
        "home, target = sys.argv[1], sys.argv[2]",
        "real, home = os.path.realpath(target), os.path.realpath(home)",
        "if real != home and not real.startswith(home + os.sep):",
        "    sys.exit('the path leads outside the home folder')",
        "content = base64.b64decode(sys.stdin.buffer.read(), validate=True)",
        "try:",
        "    os.makedirs(os.path.dirname(target), exist_ok=True)",
        "    with open(target, 'wb') as written:",
        "        written.write(content)",
        "    os.chmod(target, 0o600)",
        "except OSError as err:",
        "    sys.exit(str(err))",
    ]
)


class FilesError(RuntimeError):
    """A file could not be listed, read or written. The message says why, for the person."""


def stdout_of(completed: CommandResult, action: str) -> str:
    """`stdout`, or a `FilesError` in the computer's own words."""
    if completed.returncode != 0:
        said = completed.stderr.strip() or f"exit {completed.returncode}"
        raise FilesError(f"{action} failed: {said}")
    return completed.stdout


class Files:
    """The computer's home folder, one `docker exec` per call, as the image's own user."""

    def __init__(self, *, docker: Docker, container: str) -> None:
        self._docker = docker
        self._container = container

    async def listing(self, path: HomePath) -> Listing:
        completed = await self._run_python(
            LIST_SCRIPT, [HOME, path.absolute, path.relative], stdin=""
        )
        answer = stdout_of(completed, f"Listing ~/{path.relative}")
        try:
            entries = ENTRIES.validate_json(answer)
        except ValidationError as err:
            logger.error("the computer listed ~/%s as %r: %s", path.relative, answer, err)
            raise FilesError(
                f"The computer listed ~/{path.relative} in a form this server cannot read."
            ) from err
        return Listing(path=path.relative, entries=entries)

    async def text(self, path: HomePath) -> FileText:
        content = await self._content(path, READ_LIMIT_BYTES, "Reading")
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as err:
            raise FilesError(
                f"~/{path.relative} is not UTF-8 text, so it cannot be previewed: "
                "download it instead."
            ) from err
        return FileText(path=path.relative, content=text)

    async def download(self, path: HomePath) -> FileBytes:
        content = await self._content(path, TRANSFER_LIMIT_BYTES, "Downloading")
        return FileBytes(path=path.relative, content_base64=base64.b64encode(content).decode())

    async def upload(self, path: HomePath, content_base64: str) -> Uploaded:
        completed = await self._run_python(
            WRITE_SCRIPT, [HOME, path.absolute], stdin=content_base64
        )
        stdout_of(completed, f"Uploading ~/{path.relative}")
        return Uploaded(path=path.relative, size=len(base64.b64decode(content_base64)))

    async def _content(self, path: HomePath, limit: int, action: str) -> bytes:
        completed = await self._run_python(READ_SCRIPT, [HOME, path.absolute, str(limit)], stdin="")
        if completed.returncode == TOO_LARGE_EXIT_CODE:
            raise FilesError(f"~/{path.relative} is larger than {limit // MIB} MiB.")
        answer = stdout_of(completed, f"{action} ~/{path.relative}").strip()
        try:
            return base64.b64decode(answer, validate=True)
        except binascii.Error as err:
            logger.error("the computer sent ~/%s as %r: %s", path.relative, answer[:200], err)
            raise FilesError(
                f"The computer sent ~/{path.relative} in a form this server cannot read."
            ) from err

    async def _run_python(self, script: str, args: Sequence[str], *, stdin: str) -> CommandResult:
        return await self._docker.run(
            ["exec", "-i", self._container, "python3", "-c", script, *args],
            stdin=stdin,
            timeout_seconds=COMMAND_TIMEOUT_SECONDS,
        )
