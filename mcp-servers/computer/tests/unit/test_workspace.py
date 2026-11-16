"""Where a command starts: the folder it gives, else the workspace its call names, else home."""

from __future__ import annotations

import pytest

from computer.models.pc import HOME
from computer.models.workspace import WORKSPACE_META, start_folder


@pytest.mark.parametrize(
    "named", [None, {}, {WORKSPACE_META: "relative/path"}, {WORKSPACE_META: 7}]
)
def test_a_call_naming_no_absolute_workspace_starts_at_home(named) -> None:
    assert start_folder(None, named) == HOME


def test_a_folder_given_wins_over_the_workspace() -> None:
    assert start_folder("/tmp", {WORKSPACE_META: "/w"}) == "/tmp"
