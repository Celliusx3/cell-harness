"""The groups repository: every group read, and one added last, in its own file."""

from __future__ import annotations

import json
from pathlib import Path

from harness.bots import Group, GroupRepository

DESK = Group(id="g1", name="Desk", member_ids=("r1", "w1"))
PANEL = Group(id="g2", name="Panel", member_ids=("w1", "r1"))


def test_a_missing_file_holds_no_groups(tmp_path: Path) -> None:
    repository = GroupRepository(tmp_path / "no" / "groups.json")

    assert repository.groups() == ()


def test_an_added_group_goes_last(tmp_path: Path) -> None:
    repository = GroupRepository(tmp_path / "groups.json")
    repository.add(DESK)

    repository.add(PANEL)

    assert repository.groups() == (DESK, PANEL)


def test_a_second_repository_on_the_same_path_reads_what_the_first_wrote(tmp_path: Path) -> None:
    GroupRepository(tmp_path / "groups.json").add(DESK)

    second = GroupRepository(tmp_path / "groups.json")

    assert second.groups() == (DESK,)


def test_the_file_written_holds_only_groups(tmp_path: Path) -> None:
    GroupRepository(tmp_path / "groups.json").add(DESK)

    written = json.loads((tmp_path / "groups.json").read_text())

    assert written == {"groups": [{"id": "g1", "name": "Desk", "member_ids": ["r1", "w1"]}]}
