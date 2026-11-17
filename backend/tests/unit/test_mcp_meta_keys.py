"""The `_meta` keys MCP servers read and write by value, so they cannot follow a rename."""

from __future__ import annotations

from harness.mcp.domain.meta_keys import FILES_META, WORKSPACE_META


def test_a_call_names_its_workspace_under_the_key_servers_read() -> None:
    assert WORKSPACE_META == "harness/workspace"


def test_a_result_names_its_files_under_the_key_servers_write() -> None:
    assert FILES_META == "io.cell-harness/files"
