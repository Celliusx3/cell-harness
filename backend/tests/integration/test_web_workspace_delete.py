"""Deleting from a chat's workspace over HTTP."""

from __future__ import annotations

from harness.bots import ASSISTANT_ID
from tests.webapp import files_in

WORKSPACE = f"/api/workspaces/{ASSISTANT_ID}"


async def test_a_file_is_deleted_and_a_path_outside_is_not_found(simple, tmp_path) -> None:
    client, _, _ = simple
    made = files_in(tmp_path).workspace(ASSISTANT_ID) / "old.txt"
    made.write_bytes(b"x")

    deleted = await client.delete(WORKSPACE, params={"path": "old.txt"})
    outside = await client.delete(WORKSPACE, params={"path": ".."})

    assert deleted.status_code == 204, deleted.text
    assert not made.exists()
    assert outside.status_code == 404
