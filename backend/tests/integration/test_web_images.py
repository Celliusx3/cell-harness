"""Images the model is shown: one a real MCP server returns, and one the person attaches."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import sys
from pathlib import Path

import pytest

from harness.bots import ASSISTANT_ID
from harness.config.sections import McpServer
from harness.llm import Image, ToolMessage, UserMessage
from harness.mcp.service import McpService
from harness.tools import ToolService
from tests.integration.web_helpers import api, build, settle
from tests.mcp_stub import DOT_PNG
from tests.unit.fakes import SteppedClient, calls_tool, completed
from tests.unit.helpers import no_gate

STUB = Path(__file__).resolve().parent.parent / "mcp_stub.py"
MESSAGES = f"/api/conversations/{ASSISTANT_ID}/messages"
FILES = f"/api/conversations/{ASSISTANT_ID}/files"
DOT = base64.b64decode(DOT_PNG)
DOT_SHA256 = hashlib.sha256(DOT).hexdigest()


@pytest.fixture
async def snapshot_tool():
    store = McpService({"stub": McpServer(command=sys.executable, args=("-u", str(STUB)), env={})})
    tool_service = ToolService((), gate=no_gate())
    tool_service.add_provider(store.tools)
    await store.start()
    for _ in range(300):
        if store.statuses()[0].status != "connecting":
            break
        await asyncio.sleep(0.1)
    tool = tool_service.get("stub__snapshot")
    assert tool is not None, store.statuses()[0].error
    yield tool
    await store.aclose()


async def test_an_image_a_tool_returns_reaches_the_model_inside_its_result(
    tmp_path, snapshot_tool
) -> None:
    model = SteppedClient(calls_tool("stub__snapshot", "{}"), completed("seen"))
    service, runs = build(tmp_path, model, snapshot_tool, vision=True)
    async with api(tmp_path, service, runs) as client:
        await client.post(MESSAGES, json={"prompt": "look"})
        await settle(runs, ASSISTANT_ID)

    (result,) = [m for m in model.seen_per_call[1] if isinstance(m, ToolMessage)]
    (image,) = [block for block in result.content if isinstance(block, Image)]
    assert image.media_type == "image/png"
    assert image.sha256 == DOT_SHA256


async def test_an_image_the_person_attaches_rides_their_message(tmp_path) -> None:
    model = SteppedClient(completed("seen"))
    service, runs = build(tmp_path, model, vision=True)
    async with api(tmp_path, service, runs) as client:
        uploaded = await client.post(FILES, files={"file": ("page.png", DOT, "image/png")})
        await client.post(MESSAGES, json={"prompt": "look", "files": [uploaded.json()["path"]]})
        await settle(runs, ASSISTANT_ID)

    person = [m for m in model.seen_per_call[0] if isinstance(m, UserMessage)][-1]
    assert [image.sha256 for image in person.images] == [DOT_SHA256]
