"""A workspace asked for by a chat id that is not one plain name is not found."""

from __future__ import annotations


async def test_a_chat_id_that_is_not_a_plain_name_is_not_found(simple) -> None:
    client, _, _ = simple

    refused = await client.get("/api/workspaces/bad%00id")

    assert refused.status_code == 404
    assert "cannot name a chat's workspace" in refused.json()["detail"]
