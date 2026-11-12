"""A bot's limit of running workers is 3 unless set, and only 1 to 16 can be saved."""

from __future__ import annotations

from harness.bots import ASSISTANT_ID
from tests.integration.ticket_helpers import ticketing_app


async def test_a_bots_worker_limit_is_three_and_can_be_set_from_one_to_sixteen(tmp_path) -> None:
    world = ticketing_app(tmp_path, {})
    async with world.client as client:
        (before,) = [b for b in (await client.get("/api/bots")).json() if b["id"] == ASSISTANT_ID]
        edit = {"name": before["name"], "instructions": before["instructions"], "model": None}
        too_many = await client.put(f"/api/bots/{ASSISTANT_ID}", json={**edit, "max_workers": 17})
        none = await client.put(f"/api/bots/{ASSISTANT_ID}", json={**edit, "max_workers": 0})
        saved = await client.put(f"/api/bots/{ASSISTANT_ID}", json={**edit, "max_workers": 2})
        kept = await client.put(f"/api/bots/{ASSISTANT_ID}", json=edit)

    assert before["max_workers"] == 3
    assert (too_many.status_code, none.status_code) == (422, 422)
    assert saved.status_code == 200 and saved.json()["max_workers"] == 2
    assert kept.json()["max_workers"] == 2
