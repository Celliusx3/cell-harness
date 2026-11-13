"""A gateway with Assistant, Chef and Trader, and codes that link chats to them."""

from __future__ import annotations

import time
from pathlib import Path
from typing import NamedTuple

from harness.app_events import AppEventService
from harness.bots import Bot, BotDraft, BotRepository, BotService
from harness.channels.gateway import ChannelGateway
from harness.channels.links import ChatLinks, LinkCodes
from harness.channels.repositories.jsonl import JsonlChatRepository
from harness.runs.service.run_service import RunService
from harness.session.repository.session_repository import SessionNotFoundError
from harness.session.service.session_service import SessionService
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import durable_service, no_skills, run_service
from tests.webapp import MODEL_CREDENTIAL


class World(NamedTuple):
    gateway: ChannelGateway
    runs: RunService
    chats: JsonlChatRepository
    sessions: SessionService
    bots: BotService
    codes: LinkCodes
    links: ChatLinks
    chef: Bot
    trader: Bot


async def world(tmp_path: Path, reply: str = "hi") -> World:
    """Real stores under `tmp_path`, a model that always says `reply`, and no channel yet."""
    sessions = durable_service(tmp_path / "sessions")
    bots = BotService(
        BotRepository(tmp_path / "bots.json"),
        sessions,
        assistant_instructions="Be kind.",
        app_events=AppEventService(),
    )
    chef = await bots.create(BotDraft(name="Chef", instructions="Cook.", model=MODEL_CREDENTIAL))
    trader = await bots.create(
        BotDraft(name="Trader", instructions="Trade.", model=MODEL_CREDENTIAL)
    )
    runs = run_service(sessions, ScriptedClient(completed(reply)), bots=bots)
    chats = JsonlChatRepository(tmp_path / "chats")
    gateway = ChannelGateway(chats, runs, sessions, no_skills(), public_url="http://t")
    codes = LinkCodes(time.monotonic)
    links = ChatLinks(chats, codes, bots)
    return World(gateway, runs, chats, sessions, bots, codes, links, chef, trader)


async def prompts_in(sessions: SessionService, conversation_id: str) -> list[str]:
    """What people said in one conversation; nothing for one never written."""
    try:
        stored = await sessions.read(conversation_id)
    except SessionNotFoundError:
        return []
    return [e.message.content for e in stored.events() if e.type == "user/message"]
