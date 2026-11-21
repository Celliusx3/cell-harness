"""A workspace file's version, the rule an edit follows, and two edits to one file at once."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import pytest

from harness.files import (
    ChangedSinceReadError,
    FindMismatchError,
    TextEdit,
    WorkspaceTextRepository,
    WorkspaceTextService,
    version_of,
)
from harness.files.domain.text_edit import edited

PLAN = "# Dates\nMay\n\n# Places\nParis\n"


def service_over(tmp_path: Path) -> tuple[WorkspaceTextService, tuple[Path, ...], str]:
    folder = (tmp_path / "workspace").resolve()
    folder.mkdir()
    return WorkspaceTextService(WorkspaceTextRepository()), (folder,), str(folder / "plan.md")


def test_a_version_is_the_hex_sha256_of_the_text_s_bytes() -> None:
    text = "café ☕\n"

    assert version_of(text) == hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_an_edit_needs_find_exactly_once() -> None:
    assert edited("one two", "two", "2") == "one 2"
    with pytest.raises(FindMismatchError):
        edited("aaa", "aa", "b")


async def test_an_edit_that_fails_leaves_the_file_as_it_was(tmp_path: Path) -> None:
    service, roots, path = service_over(tmp_path)
    await service.write(roots, path, "one\none\n", "s")

    with pytest.raises(FindMismatchError):
        await service.edit(roots, path, TextEdit(find="one", replace="two"), "s")

    assert Path(path).read_bytes() == b"one\none\n"


async def test_two_edits_at_once_to_different_paragraphs_both_survive(tmp_path: Path) -> None:
    service, roots, path = service_over(tmp_path)
    await service.write(roots, path, PLAN, "s")

    await asyncio.gather(
        service.edit(roots, path, TextEdit(find="May", replace="June"), "s"),
        service.edit(roots, path, TextEdit(find="Paris", replace="Rome"), "s"),
    )

    assert Path(path).read_text() == "# Dates\nJune\n\n# Places\nRome\n"
    assert [p.name for p in Path(path).parent.iterdir()] == ["plan.md"]


async def test_of_two_workers_editing_at_once_the_second_reads_again_and_both_survive(
    tmp_path: Path,
) -> None:
    service, roots, path = service_over(tmp_path)
    await service.write(roots, path, PLAN, "bot")
    await service.read(roots, path, "w1")
    await service.read(roots, path, "w2")

    first, second = await asyncio.gather(
        service.edit(roots, path, TextEdit(find="May", replace="June"), "w1"),
        service.edit(roots, path, TextEdit(find="Paris", replace="Rome"), "w2"),
        return_exceptions=True,
    )
    await service.read(roots, path, "w2")
    await service.edit(roots, path, TextEdit(find="Paris", replace="Rome"), "w2")

    assert isinstance(first, Path)
    assert isinstance(second, ChangedSinceReadError)
    assert Path(path).read_text() == "# Dates\nJune\n\n# Places\nRome\n"
