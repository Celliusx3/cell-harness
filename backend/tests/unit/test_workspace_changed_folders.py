"""A batch of changed paths becomes each distinct folder that holds one, inside the workspace."""

from __future__ import annotations

from pathlib import PurePath

from harness.files.domain.models import changed_folders

WORKSPACE = PurePath("/files/workspaces/bot-1")


def test_each_changed_path_names_its_parent_once_children_before_parents() -> None:
    changed = [
        WORKSPACE / "out" / "report.pdf",
        WORKSPACE / "out" / "notes.txt",
        WORKSPACE / "out",
        WORKSPACE / "out" / "charts" / "a.png",
    ]

    assert changed_folders(WORKSPACE, changed) == ("out/charts", "out", "")


def test_the_workspace_itself_and_a_path_outside_it_are_dropped() -> None:
    changed = [WORKSPACE, PurePath("/elsewhere/secret.txt"), WORKSPACE.parent / "bot-2" / "x"]

    assert changed_folders(WORKSPACE, changed) == ()
