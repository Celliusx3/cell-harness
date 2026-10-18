"""An image a chat showed the model, served back by its hash only to that chat."""

from __future__ import annotations

import base64
import hashlib

import httpx
import pytest

from harness.bots import ASSISTANT_ID
from harness.llm import UserMessage
from harness.prompts import ATTACHED_FILE
from tests.integration.web_helpers import api, build, settle
from tests.mcp_stub import DOT_PNG
from tests.unit.fakes import SteppedClient, completed

DOT = base64.b64decode(DOT_PNG)
DOT_SHA256 = hashlib.sha256(DOT).hexdigest()
RESEARCHER = {"name": "Researcher", "instructions": "Find sources and cite every claim."}


def chat(chat_id: str) -> str:
    return f"/api/conversations/{chat_id}"


async def send_image(client: httpx.AsyncClient, chat_id: str) -> str:
    """Attach the one-pixel PNG to a message in `chat_id`; the path it was saved at."""
    uploaded = await client.post(
        f"{chat(chat_id)}/files", files={"file": ("page.png", DOT, "image/png")}
    )
    path = uploaded.json()["path"]
    sent = await client.post(f"{chat(chat_id)}/messages", json={"prompt": "look", "files": [path]})
    assert sent.status_code == 202, sent.text
    return path


async def test_an_image_is_served_inline_to_the_chat_whose_log_names_it(tmp_path) -> None:
    service, runs = build(tmp_path, SteppedClient(completed("seen")), vision=True)
    async with api(tmp_path, service, runs) as client:
        await send_image(client, ASSISTANT_ID)
        await settle(runs, ASSISTANT_ID)

        served = await client.get(f"{chat(ASSISTANT_ID)}/images/{DOT_SHA256}")

    assert served.status_code == 200
    assert served.content == DOT
    assert served.headers["content-type"] == "image/png"
    assert served.headers["x-content-type-options"] == "nosniff"
    assert served.headers["content-disposition"].startswith("inline")


async def test_a_hash_only_another_chat_s_log_names_is_not_served(tmp_path) -> None:
    service, runs = build(tmp_path, SteppedClient(completed("seen")), vision=True)
    async with api(tmp_path, service, runs) as client:
        researcher = (await client.post("/api/bots", json=RESEARCHER)).json()["id"]
        await client.post(f"{chat(researcher)}/messages", json={"prompt": "hi"})
        await settle(runs, researcher)
        await send_image(client, ASSISTANT_ID)
        await settle(runs, ASSISTANT_ID)

        served = await client.get(f"{chat(researcher)}/images/{DOT_SHA256}")

    assert served.status_code == 404
    assert served.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize("name", ["abc", DOT_SHA256.upper(), "g" * 64, DOT_SHA256 + "0"])
async def test_a_name_that_is_not_a_hash_is_not_served(tmp_path, name: str) -> None:
    service, runs = build(tmp_path, SteppedClient(completed("seen")), vision=True)
    async with api(tmp_path, service, runs) as client:
        await send_image(client, ASSISTANT_ID)
        await settle(runs, ASSISTANT_ID)

        served = await client.get(f"{chat(ASSISTANT_ID)}/images/{name}")

    assert served.status_code == 404


async def test_a_named_image_whose_file_is_gone_is_not_served(tmp_path) -> None:
    service, runs = build(tmp_path, SteppedClient(completed("seen")), vision=True)
    async with api(tmp_path, service, runs) as client:
        await send_image(client, ASSISTANT_ID)
        await settle(runs, ASSISTANT_ID)
        (tmp_path / "sessions" / "blobs" / f"{DOT_SHA256}.png").unlink()

        served = await client.get(f"{chat(ASSISTANT_ID)}/images/{DOT_SHA256}")

    assert served.status_code == 404


async def test_without_vision_an_attached_image_is_only_its_line(tmp_path) -> None:
    model = SteppedClient(completed("seen"))
    service, runs = build(tmp_path, model, vision=False)
    async with api(tmp_path, service, runs) as client:
        path = await send_image(client, ASSISTANT_ID)
        await settle(runs, ASSISTANT_ID)

        served = await client.get(f"{chat(ASSISTANT_ID)}/images/{DOT_SHA256}")

    person = [m for m in model.seen_per_call[0] if isinstance(m, UserMessage)][-1]
    line = ATTACHED_FILE.format(name="page.png", media_type="image/png", size=len(DOT), path=path)
    assert person == UserMessage(content=f"look\n\n{line}")
    assert served.status_code == 404
    assert not (tmp_path / "sessions" / "blobs").exists()
