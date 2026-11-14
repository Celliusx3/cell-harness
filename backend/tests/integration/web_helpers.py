"""Building and reading the HTTP surface in-process, for `test_web*.py`."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import httpx

from harness.app_events import AppEventService
from harness.bots import ASSISTANT_ID, MENTION_TURN_ORDER, BotRepository, BotService, GroupService
from harness.llm import StreamEvent
from harness.runs.service.bot_messages import BotMessenger
from harness.runs.service.run_service import RunService
from harness.runtime.service import Runtime
from harness.session.service.session_service import SessionService
from harness.tools import Tool, ToolService, Toolset
from harness.tools.native.bots import MESSAGE_BOT
from harness.web.runtime import attach_bot_messages
from tests.unit.fakes import OneModel, PerBotClient
from tests.unit.helpers import (
    durable_service,
    heard_nowhere,
    no_approvals,
    no_images,
    no_skills,
    run_service,
)
from tests.webapp import a_model_saved_in, bots_in, images_in, web_app

ASSISTANT_START = "ASSISTANT"


def build(tmp_path, client, *tools, vision: bool = False) -> tuple[SessionService, RunService]:
    service = durable_service(tmp_path / "sessions")
    runs = run_service(
        service,
        client,
        *tools,
        bots=bots_in(tmp_path, service),
        images=images_in(tmp_path) if vision else None,
    )
    return service, runs


def api(tmp_path, service: SessionService, runs: RunService) -> httpx.AsyncClient:
    app = web_app(tmp_path, service, runs, skills=no_skills(), secrets=a_model_saved_in(tmp_path))
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://harness.test")


async def assistant_chat(client: httpx.AsyncClient, prompt: str) -> str:
    """Assistant's chat, once `prompt` has been sent to it."""
    sent = await client.post(f"/api/conversations/{ASSISTANT_ID}/messages", json={"prompt": prompt})
    assert sent.status_code == 202, sent.text
    return ASSISTANT_ID


async def settle(runs: RunService, conversation_id: str) -> None:
    run = runs.active_run(conversation_id)
    if run is not None:
        await asyncio.wait_for(run._settle_task, timeout=5)


def events_from(body: str) -> list[dict]:
    """The `session` frames of an SSE body, decoded."""
    frames = [block for block in body.split("\n\n") if block.strip()]
    return [
        json.loads(block.split("data: ", 1)[1])
        for block in frames
        if block.startswith("event: session")
    ]


def frame_names(body: str) -> list[str]:
    return [
        block.split("event: ", 1)[1].split("\n", 1)[0]
        for block in body.split("\n\n")
        if block.strip()
    ]


@dataclass(frozen=True)
class Messaging:
    """An app whose bots can message each other, and the parts a test reaches into."""

    client: httpx.AsyncClient
    model: PerBotClient
    runs: RunService
    messages: BotMessenger
    service: SessionService


def messaging_app(
    tmp_path, scripts: Mapping[str, Sequence[Sequence[StreamEvent]]], *tools: Tool
) -> Messaging:
    """Assistant and the bots a test makes, each answered from `scripts`."""
    model = PerBotClient(scripts)
    service = durable_service(tmp_path / "sessions")
    app_events = AppEventService()
    bots = BotService(
        BotRepository(tmp_path / "bots.json"),
        service,
        assistant_instructions=ASSISTANT_START,
        app_events=app_events,
    )
    tool_service = ToolService(tools, approvals=no_approvals())
    offered = (MESSAGE_BOT, *(tool.name for tool in tools))
    runtime = Runtime(
        models=OneModel(model),
        images=no_images(),
        tools=Toolset(tool_service, offered, sight_tools=frozenset()),
        guidance="GUIDE",
        checkpoint=service.flush,
    )
    runs = RunService(
        service,
        runtime,
        bots,
        GroupService(bots, service, MENTION_TURN_ORDER),
        app_events=app_events,
    )
    messages = attach_bot_messages(tool_service, bots, runs, follow=heard_nowhere)
    secrets = a_model_saved_in(tmp_path)
    app = web_app(tmp_path, service, runs, skills=no_skills(), bots=bots, secrets=secrets)
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")
    return Messaging(client, model, runs, messages, service)


async def send(client: httpx.AsyncClient, chat: str, prompt: str) -> None:
    """Send `prompt` to `chat` as the person."""
    sent = await client.post(f"/api/conversations/{chat}/messages", json={"prompt": prompt})
    assert sent.status_code == 202, sent.text


async def once_said(client: httpx.AsyncClient, chat: str, said: str) -> list[dict]:
    """The chat's events once its last reply is `said` and no turn is running."""
    for _ in range(500):
        detail = (await client.get(f"/api/conversations/{chat}")).json()
        replies = [e for e in detail["events"] if e["type"] == "assistant/message"]
        if not detail["running"] and replies and replies[-1]["message"]["content"] == said:
            return detail["events"]
        await asyncio.sleep(0.01)
    raise AssertionError(f"{chat} never said {said!r}")


def of_type(events: list[dict], kind: str) -> list[dict]:
    """The events of one `type`, in order."""
    return [event for event in events if event["type"] == kind]
