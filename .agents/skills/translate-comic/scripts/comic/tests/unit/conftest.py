"""The one-bubble comic, the fake PhotoCraft, and the settings that reach it."""

from __future__ import annotations

from pathlib import Path

import pytest

from comic.cli import LOCK_NAME
from comic.steps.write import PhotoCraftAccess
from comic.tests.unit.fake_photocraft import TOKEN, FakePhotoCraft
from comic.tests.unit.one_bubble import saved_bubble_page


@pytest.fixture
def bubble_comic(tmp_path: Path) -> Path:
    return saved_bubble_page(tmp_path / "ch1.png")


@pytest.fixture
def photocraft() -> FakePhotoCraft:
    return FakePhotoCraft()


@pytest.fixture
def access(photocraft: FakePhotoCraft, tmp_path: Path) -> PhotoCraftAccess:
    return PhotoCraftAccess(addr=photocraft.addr, token=TOKEN, lock=tmp_path / LOCK_NAME)
