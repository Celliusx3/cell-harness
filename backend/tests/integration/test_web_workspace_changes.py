"""A chat's workspace changes, streamed while a panel watches it, against a real server."""

from __future__ import annotations

from harness.bots import ASSISTANT_ID
from tests.integration.test_web_app_events import next_frame
from tests.integration.test_web_stream import served
from tests.unit.fakes import SteppedClient, completed
from tests.webapp import files_in

CHANGES = f"/api/workspaces/{ASSISTANT_ID}/changes"


async def test_a_file_written_while_watched_names_its_folder(tmp_path) -> None:
    workspace = files_in(tmp_path).workspace(ASSISTANT_ID)
    (workspace / "out").mkdir()
    async with (
        served(tmp_path, SteppedClient(completed("hi"))) as (client, _, _),
        client.stream("GET", CHANGES) as response,
    ):
        chunks, buffer = response.aiter_text(), [""]
        watching = await next_frame(chunks, buffer)
        (workspace / "out" / "report.pdf").write_bytes(b"%PDF")
        changed = await next_frame(chunks, buffer)

    assert watching == ("workspace/watching", {"type": "workspace/watching"})
    assert changed == ("workspace/changed", {"type": "workspace/changed", "folder": "out"})
