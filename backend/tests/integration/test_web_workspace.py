"""A chat's workspace over HTTP: one folder listed, and a path outside it refused."""

from __future__ import annotations

from harness.bots import ASSISTANT_ID
from tests.webapp import files_in

LISTING = f"/api/workspaces/{ASSISTANT_ID}"


async def test_a_workspace_folder_is_listed(simple, tmp_path) -> None:
    client, _, _ = simple
    workspace = files_in(tmp_path).workspace(ASSISTANT_ID)
    (workspace / "report.pdf").write_bytes(b"%PDF")

    listed = await client.get(LISTING, params={"path": ""})

    assert listed.status_code == 200, listed.text
    body = listed.json()
    (entry,) = body["entries"]
    assert body["path"] == ""
    assert body["workspace"] == str(workspace)
    assert entry.pop("modified").endswith("Z")
    assert entry == {"name": "report.pdf", "kind": "file", "size": 4}


async def test_a_path_outside_the_workspace_is_not_found(simple) -> None:
    client, _, _ = simple

    assert (await client.get(LISTING, params={"path": ".."})).status_code == 404
