"""A chat's files over HTTP: uploading one, reading one back, and sending a message with them."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import replace
from pathlib import Path

import httpx

from harness.bots import ASSISTANT_ID
from harness.config.settings import Settings
from harness.web.server import build_channels
from tests.integration.web_helpers import api, build, of_type, once_said, settle
from tests.unit.fakes import ScriptedClient, SteppedClient, calls_tool, completed, gated_tool
from tests.unit.helpers import no_skills
from tests.webapp import channel_services, files_in, secrets_in, web_app

PNG_HEADER = b"\x89PNG\r\n\x1a\n"
FILES = f"/api/conversations/{ASSISTANT_ID}/files"
FILE = f"/api/conversations/{ASSISTANT_ID}/file"
MESSAGES = f"/api/conversations/{ASSISTANT_ID}/messages"


async def upload(client: httpx.AsyncClient, name: str, body: bytes) -> httpx.Response:
    return await client.post(FILES, files={"file": (name, body, "application/octet-stream")})


async def chunks_of(body: bytes) -> AsyncIterator[bytes]:
    yield body


async def test_an_upload_is_saved_in_the_chat_s_folder_and_returned(simple, tmp_path) -> None:
    client, _, _ = simple

    sent = await upload(client, "page.png", PNG_HEADER)

    assert sent.status_code == 201, sent.text
    stored = sent.json()
    path = Path(stored["path"])
    assert path.read_bytes() == PNG_HEADER
    assert path.parent.parent == (tmp_path / "files" / ASSISTANT_ID).resolve()
    assert stored == {"path": str(path), "name": "page.png", "media_type": "image/png", "size": 8}


async def test_an_upload_to_a_chat_no_bot_has_is_a_404(simple, tmp_path) -> None:
    client, _, _ = simple

    sent = await client.post("/api/conversations/nope/files", files={"file": ("a.png", b"x")})

    assert sent.status_code == 404
    assert not (tmp_path / "files" / "nope").exists()


async def test_an_upload_over_the_limit_is_a_413_and_leaves_nothing(tmp_path) -> None:
    service, runs = build(tmp_path, ScriptedClient(completed("hi")))
    files = files_in(tmp_path, max_bytes=8)
    app = web_app(tmp_path, service, runs, skills=no_skills(), files=files)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://harness.test"
    ) as client:
        sent = await upload(client, "big.png", PNG_HEADER + b"!")

    assert sent.status_code == 413
    assert "big.png" in sent.json()["detail"]
    assert list((tmp_path / "files").rglob("*")) == [tmp_path / "files" / ASSISTANT_ID]


async def test_a_name_that_climbs_is_saved_as_its_last_part(simple, tmp_path) -> None:
    client, _, _ = simple

    sent = await upload(client, "../../x.png", PNG_HEADER)

    assert sent.status_code == 201
    path = Path(sent.json()["path"])
    assert path.name == "x.png"
    assert path.parent.parent == (tmp_path / "files" / ASSISTANT_ID).resolve()


async def test_a_name_with_nothing_to_save_under_is_a_422(simple) -> None:
    client, _, _ = simple

    assert (await upload(client, "..", PNG_HEADER)).status_code == 422
    assert (await upload(client, "", PNG_HEADER)).status_code == 422


async def test_an_image_in_the_chat_s_folder_is_shown_in_place(simple) -> None:
    client, _, _ = simple
    stored = (await upload(client, "page.png", PNG_HEADER)).json()

    read = await client.get(FILE, params={"path": stored["path"]})

    assert read.status_code == 200
    assert read.content == PNG_HEADER
    assert read.headers["content-type"] == "image/png"
    assert read.headers["content-disposition"].startswith("inline")
    assert read.headers["x-content-type-options"] == "nosniff"


async def test_anything_but_an_image_is_downloaded_never_shown(simple) -> None:
    client, _, _ = simple
    stored = (await upload(client, "page.html", b"<script>1</script>")).json()

    read = await client.get(FILE, params={"path": stored["path"]})

    assert read.status_code == 200
    assert read.headers["content-disposition"].startswith("attachment")
    assert read.headers["x-content-type-options"] == "nosniff"


async def test_a_path_outside_the_chat_s_folder_is_a_404(simple, tmp_path) -> None:
    client, _, _ = simple
    other_chat = files_in(tmp_path)
    theirs = await other_chat.save("other", "page.png", chunks_of(PNG_HEADER))
    mine = (await upload(client, "page.png", PNG_HEADER)).json()
    climbing = f"{Path(mine['path']).parent}/../../other/{Path(theirs.path).parent.name}/page.png"

    for path in (theirs.path, "/etc/hosts", climbing, "page.png"):
        read = await client.get(FILE, params={"path": path})
        assert read.status_code == 404, path
        assert read.headers["x-content-type-options"] == "nosniff"


async def test_a_message_naming_a_file_outside_the_chat_s_folder_is_a_422(simple) -> None:
    client, _, _ = simple

    sent = await client.post(MESSAGES, json={"prompt": "look", "files": ["/etc/hosts"]})

    assert sent.status_code == 422
    assert "/etc/hosts" in sent.json()["detail"]


async def test_a_message_with_an_uploaded_file_logs_it(simple) -> None:
    client, service, runs = simple
    stored = (await upload(client, "page.png", PNG_HEADER)).json()

    sent = await client.post(MESSAGES, json={"prompt": "look", "files": [stored["path"]]})
    await settle(runs, ASSISTANT_ID)

    assert sent.status_code == 202
    detail = (await client.get(f"/api/conversations/{ASSISTANT_ID}")).json()
    (said,) = of_type(detail["events"], "user/message")
    assert said["files"] == [stored]


async def test_a_message_queued_behind_a_turn_keeps_its_files(tmp_path) -> None:
    release = asyncio.Event()
    model = SteppedClient(
        calls_tool("gate", '{"value": "x"}'), completed("first"), completed("second")
    )
    service, runs = build(tmp_path, model, gated_tool(release))
    async with api(tmp_path, service, runs) as client:
        await client.post(MESSAGES, json={"prompt": "go"})
        stored = (await upload(client, "page.png", PNG_HEADER)).json()
        queued = await client.post(MESSAGES, json={"prompt": "and", "files": [stored["path"]]})
        release.set()
        events = await once_said(client, ASSISTANT_ID, "second")

    assert queued.json()["queued"] is True
    assert [said["files"] for said in of_type(events, "user/message")] == [[], [stored]]


def test_the_web_channel_keeps_files_in_the_service_it_is_built_with(tmp_path) -> None:
    sessions, runs = build(tmp_path, ScriptedClient([]))
    files = files_in(tmp_path)
    settings = Settings(local_settings_path=tmp_path / "config.local.json")
    services = replace(channel_services(tmp_path, sessions, runs), files=files)

    _, web = build_channels(settings, services, secrets_in(tmp_path))

    assert web.files is files
