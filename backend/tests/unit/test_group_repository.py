"""The groups repository: every group read, and one added last, in its own file."""

from __future__ import annotations

import json
from pathlib import Path

from harness.groups import Group, JsonGroupRepository

DESK = Group(id="g1", name="Desk", member_ids=("r1", "w1"))
PANEL = Group(id="g2", name="Panel", member_ids=("w1", "r1"))


def test_a_missing_file_holds_no_groups(tmp_path: Path) -> None:
    repository = JsonGroupRepository(tmp_path / "no" / "groups.json")

    assert repository.all() == ()


def test_an_added_group_goes_last(tmp_path: Path) -> None:
    repository = JsonGroupRepository(tmp_path / "groups.json")
    repository.add(DESK)

    repository.add(PANEL)

    assert repository.all() == (DESK, PANEL)


def test_an_updated_group_replaces_the_one_with_its_id_in_place(tmp_path: Path) -> None:
    repository = JsonGroupRepository(tmp_path / "groups.json")
    repository.add(DESK)
    repository.add(PANEL)
    renamed = DESK.model_copy(update={"name": "Trading desk", "lead_id": "w1"})

    repository.update(renamed)

    assert repository.all() == (renamed, PANEL)


def test_a_second_repository_on_the_same_path_reads_what_the_first_wrote(tmp_path: Path) -> None:
    JsonGroupRepository(tmp_path / "groups.json").add(DESK)

    second = JsonGroupRepository(tmp_path / "groups.json")

    assert second.all() == (DESK,)


def test_the_file_written_holds_only_groups(tmp_path: Path) -> None:
    JsonGroupRepository(tmp_path / "groups.json").add(DESK)

    written = json.loads((tmp_path / "groups.json").read_text())

    assert written == {
        "groups": [
            {
                "id": "g1",
                "name": "Desk",
                "member_ids": ["r1", "w1"],
                "lead_id": None,
                "reply": "everyone",
                "auto_model": None,
            }
        ]
    }
