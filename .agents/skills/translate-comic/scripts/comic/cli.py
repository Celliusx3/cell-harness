"""The command line: `pages`, `write` and `cleanup`, each printing one JSON object or one error."""

from __future__ import annotations

import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TextIO

from pydantic import ValidationError

from comic import ComicError
from comic.chapter.pages import ITEMS, Item
from comic.connection import PhotoCraftError
from comic.models import CleanupResult, PagesResult, WriteResult
from comic.steps import work_folder
from comic.steps.cleanup import clean_up_work_folder
from comic.steps.pages import list_pages
from comic.steps.write import PhotoCraftAccess, write_page

USAGE = (
    "usage: run.py pages <file> | run.py write <work> <page> (the items as JSON on stdin) "
    "| run.py cleanup <work> <keep>"
)
ACCESS = ("PHOTOCRAFT_ADDR", "PHOTOCRAFT_TOKEN")
LOCK_NAME = ".photocraft.lock"
FAILURES = (ComicError, PhotoCraftError, OSError, ValidationError, zipfile.BadZipFile)


def access_of(env: Mapping[str, str]) -> PhotoCraftAccess:
    """PhotoCraft's address and token from `env`, its lock in `HOME`; refused when unset."""
    values = {name: env.get(name, "").strip() for name in ACCESS}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ComicError(
            f"{', '.join(missing)} not set; PhotoCraft is not set up for the bots' computer: "
            "install photocraft-cli on the Mac that runs the app, then restart the app"
        )
    home = env.get("HOME", "").strip()
    if not home:
        raise ComicError("HOME is not set, so PhotoCraft's lock has no folder to go in")
    return PhotoCraftAccess(
        addr=values["PHOTOCRAFT_ADDR"],
        token=values["PHOTOCRAFT_TOKEN"],
        lock=Path(home) / LOCK_NAME,
    )


def validation_problems(invalid: ValidationError) -> str:
    """Each problem a validation found, where it is and what it is, on one line."""
    return "; ".join(
        f"{'.'.join(str(at) for at in error['loc'])}: {error['msg']}"
        if error["loc"]
        else error["msg"]
        for error in invalid.errors()
    )


def items_of(text: str) -> list[Item]:
    """The items sent on stdin; refused saying which field of which item is wrong."""
    try:
        return ITEMS.validate_json(text)
    except ValidationError as invalid:
        raise ComicError(
            f"the items on stdin are not valid: {validation_problems(invalid)}"
        ) from invalid


def one_line(failure: Exception) -> str:
    """The failure as the one line after `error:`."""
    if isinstance(failure, ValidationError):
        return f"{failure.title} is not as the scripts wrote it: {validation_problems(failure)}"
    return " ".join(str(failure).splitlines())


def command_result(
    argv: Sequence[str], env: Mapping[str, str], stdin: TextIO
) -> PagesResult | WriteResult | CleanupResult:
    """The result of the command `argv` names; refused with the usage when it names none."""
    match list(argv):
        case ["pages", path]:
            return list_pages(path)
        case ["write", work, page]:
            access = access_of(env)
            return write_page(access, work_folder(work), page, items_of(stdin.read()))
        case ["cleanup", work, keep]:
            return clean_up_work_folder(work, keep)
        case _:
            raise ComicError(USAGE)


def main(argv: Sequence[str], env: Mapping[str, str], stdin: TextIO, stdout: TextIO) -> int:
    """Print the command's JSON result and return 0, or print one `error:` line and return 1."""
    try:
        result = command_result(argv, env, stdin)
    except FAILURES as failure:
        stdout.write(f"error: {one_line(failure)}\n")
        return 1
    stdout.write(result.model_dump_json() + "\n")
    return 0
