"""Every path a command names must be absolute, and is resolved before it is used."""

from __future__ import annotations

from pathlib import Path

import pytest

from comic import ComicError
from comic.steps import absolute_path


def test_an_absolute_path_is_resolved(tmp_path: Path) -> None:
    (tmp_path / "bot").mkdir()

    assert (
        absolute_path(str(tmp_path / "bot" / ".." / "bot" / "ch1.cbz"))
        == tmp_path / "bot" / "ch1.cbz"
    )


def test_a_relative_path_is_refused() -> None:
    with pytest.raises(ComicError, match="ch1.cbz is not an absolute path"):
        absolute_path("ch1.cbz")
