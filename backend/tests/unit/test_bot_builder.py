"""Bot builder: built in beside Assistant, and its instructions name tools that exist."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.app_events import AppEventService
from harness.bots import (
    BUILDER_ID,
    BUILDER_NAME,
    Bot,
    BotRepository,
    BotService,
    BuiltInBotError,
)
from harness.prompts import BUILDER_INSTRUCTIONS
from harness.session.domain.models import BotInstructionsEvent
from harness.session.service.session_service import SessionService
from harness.tools.native.bots import BOT_CREATE
from harness.tools.native.tickets import TICKET_ROUTE
from tests.unit.helpers import durable_service

BUILDER = Bot(id=BUILDER_ID, name=BUILDER_NAME, instructions=BUILDER_INSTRUCTIONS)


@pytest.fixture
def service(tmp_path: Path) -> SessionService:
    return durable_service(tmp_path / "sessions")


@pytest.fixture
def bots(tmp_path: Path, service: SessionService) -> BotService:
    return BotService(
        BotRepository(tmp_path / "bots.json"),
        service,
        assistant_instructions="Be kind.",
        app_events=AppEventService(),
    )


async def test_the_builder_can_be_neither_archived_nor_deleted(bots: BotService) -> None:
    with pytest.raises(BuiltInBotError):
        bots.archive(BUILDER_ID)
    with pytest.raises(BuiltInBotError):
        await bots.delete(BUILDER_ID)

    assert bots.active_bot(BUILDER_ID) == BUILDER


async def test_listing_opens_the_builder_s_chat_only_the_first_time(
    bots: BotService, service: SessionService
) -> None:
    await bots.open_active_bots()
    await bots.open_active_bots()

    chat = await service.read(BUILDER_ID)
    assert list(chat.events()) == [
        BotInstructionsEvent(
            name=BUILDER_NAME, instructions=BUILDER_INSTRUCTIONS, bot_id=BUILDER_ID
        )
    ]


def test_the_instructions_name_the_tools_by_their_real_names() -> None:
    assert BOT_CREATE in BUILDER_INSTRUCTIONS
    assert TICKET_ROUTE in BUILDER_INSTRUCTIONS
