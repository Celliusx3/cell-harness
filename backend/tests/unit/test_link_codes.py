"""A code from a bot's page links a direct chat to that bot; an unlinked chat is silent."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from harness.bots import ASSISTANT_ID, BotDraft, BotService
from harness.channels.gateway import ChannelGateway
from harness.channels.links import LINK_CODE_SECONDS, ChatLinks, LinkCodes
from harness.channels.protocol import InboundMessage
from harness.channels.repositories.jsonl import JsonlChatRepository
from harness.channels.repository import ChatState
from harness.secrets import DiskSecretRepository, SecretService
from harness.secrets.models.details import TelegramDetails
from harness.session.models import UserMessageEvent
from harness.web.routes.link_codes import build_router
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import durable_service, no_skills, run_service

KEY = "0123456789abcdef0123456789abcdef"
WRONG_GUESSES = 5


class Clock:
    """A clock the test moves by hand."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class UnlinkedPlatform:
    """A platform whose chats write nowhere until they are linked."""

    @property
    def channel(self) -> str:
        return "telegram"

    def conversation_for(self, chat_id: str) -> str:
        return ""

    async def run(self) -> None:
        await asyncio.Event().wait()


def test_a_code_is_six_digits_and_names_its_bot() -> None:
    codes = LinkCodes(Clock())

    code = codes.issue("chef", "telegram")

    assert re.fullmatch(r"\d{6}", code.code)
    assert codes.redeem("telegram", "1", code.code) == "chef"


def test_a_code_works_once() -> None:
    codes = LinkCodes(Clock())
    code = codes.issue("chef", "telegram")
    codes.redeem("telegram", "1", code.code)

    assert codes.redeem("telegram", "2", code.code) is None


def test_a_code_lasts_fifteen_minutes() -> None:
    clock = Clock()
    codes = LinkCodes(clock)
    code = codes.issue("chef", "telegram")

    clock.now += LINK_CODE_SECONDS + 1

    assert LINK_CODE_SECONDS == 15 * 60
    assert codes.redeem("telegram", "1", code.code) is None


def test_a_code_for_telegram_does_not_link_discord() -> None:
    codes = LinkCodes(Clock())
    code = codes.issue("chef", "telegram")

    assert codes.redeem("discord", "1", code.code) is None
    assert codes.redeem("telegram", "1", code.code) == "chef"


def test_only_a_message_that_is_exactly_the_code_links() -> None:
    codes = LinkCodes(Clock())
    code = codes.issue("chef", "telegram")

    assert codes.redeem("telegram", "1", f"my code is {code.code}") is None
    assert codes.redeem("telegram", "1", f" {code.code}\n") == "chef"


def test_a_chat_that_guesses_wrong_five_times_is_ignored() -> None:
    codes = LinkCodes(Clock())
    code = codes.issue("chef", "telegram")
    for step in range(1, WRONG_GUESSES + 1):
        codes.redeem("telegram", "1", f"{(int(code.code) + step) % 10**6:06d}")

    assert codes.redeem("telegram", "1", code.code) is None
    assert codes.redeem("telegram", "2", code.code) == "chef"


@pytest.fixture
async def world(tmp_path: Path):
    sessions = durable_service(tmp_path / "sessions")
    bots = BotService(tmp_path / "bots.json", sessions, assistant_instructions="Be kind.")
    chef = await bots.create(BotDraft(name="Chef", instructions="Cook."))
    trader = await bots.create(BotDraft(name="Trader", instructions="Trade."))
    runs = run_service(sessions, ScriptedClient(completed("hi")), bots=bots)
    chats = JsonlChatRepository(tmp_path / "chats")
    gateway = ChannelGateway(chats, runs, sessions, no_skills(), public_url="http://t")
    gateway.register(UnlinkedPlatform())
    codes = LinkCodes(Clock())
    yield {
        "gateway": gateway,
        "runs": runs,
        "chats": chats,
        "sessions": sessions,
        "codes": codes,
        "links": ChatLinks(chats, codes, bots),
        "bots": bots,
        "chef": chef,
        "trader": trader,
    }
    await runs.aclose()
    await gateway.aclose()


def _hi(chat_id: str = "1") -> InboundMessage:
    return InboundMessage(channel="telegram", chat_id=chat_id, text="hi")


async def _settled(run) -> None:
    for _ in range(200):
        if run.settled:
            return
        await asyncio.sleep(0.01)
    raise AssertionError("the turn never settled")


async def test_a_code_links_a_direct_chat_to_its_bot(world) -> None:
    code = world["codes"].issue(world["chef"].id, "telegram")

    linked = await world["links"].link_if_code("telegram", "1", code.code)
    run = await world["gateway"].receive(_hi())

    assert linked is not None and linked.name == "Chef"
    assert run is not None and run.session.id == world["chef"].id


async def test_a_new_code_moves_the_chat(world) -> None:
    first = world["codes"].issue(world["chef"].id, "telegram")
    await world["links"].link_if_code("telegram", "1", first.code)
    second = world["codes"].issue(world["trader"].id, "telegram")

    await world["links"].link_if_code("telegram", "1", second.code)
    run = await world["gateway"].receive(_hi())

    assert run is not None and run.session.id == world["trader"].id


async def test_an_unknown_code_links_nothing(world) -> None:
    linked = await world["links"].link_if_code("telegram", "1", "000000")

    assert linked is None
    assert await world["gateway"].receive(_hi()) is None


async def test_text_that_is_not_a_code_links_nothing(world) -> None:
    assert await world["links"].link_if_code("telegram", "1", "hello") is None


async def test_an_unlinked_direct_chat_gets_no_turn(world) -> None:
    run = await world["gateway"].receive(_hi())

    assert run is None
    assert world["runs"].active(ASSISTANT_ID) is None


async def test_a_chat_stored_before_links_keeps_the_assistant(world) -> None:
    stored = ChatState(channel="telegram", chat_id="1", conversation_id=ASSISTANT_ID)
    await world["chats"].save(stored)

    run = await world["gateway"].receive(_hi())

    assert run is not None and run.session.id == ASSISTANT_ID


async def test_an_unlinked_chat_cannot_clear_the_assistant(world) -> None:
    legacy = ChatState(channel="telegram", chat_id="2", conversation_id=ASSISTANT_ID)
    await world["chats"].save(legacy)
    await _settled(await world["gateway"].receive(_hi("2")))

    await world["gateway"].clear("telegram", "1")

    session = await world["sessions"].resume(ASSISTANT_ID)
    said = [e.message.content for e in session.events() if isinstance(e, UserMessageEvent)]
    assert said == ["hi"]


@pytest.fixture
def keyring(tmp_path: Path) -> SecretService:
    return SecretService(DiskSecretRepository(tmp_path / "secrets.json"), encryption_key=KEY)


async def _ask_for_code(world, keyring, bot_id: str, platform: str) -> httpx.Response:
    app = FastAPI()
    app.include_router(build_router(world["codes"], world["bots"], keyring))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as http:
        return await http.post(f"/api/bots/{bot_id}/link-codes", json={"platform": platform})


async def test_a_bots_page_gets_a_code_for_that_bot(world, keyring) -> None:
    keyring.add_credential("telegram", TelegramDetails(), SecretStr("123456:AAtelegram-1111"))

    response = await _ask_for_code(world, keyring, world["chef"].id, "telegram")

    body = response.json()
    assert response.status_code == 201
    assert (body["bot_name"], body["expires_in_seconds"]) == ("Chef", LINK_CODE_SECONDS)
    assert world["codes"].redeem("telegram", "1", body["code"]) == world["chef"].id


async def test_a_code_for_a_platform_with_no_token_is_refused(world, keyring) -> None:
    response = await _ask_for_code(world, keyring, world["chef"].id, "discord")

    assert response.status_code == 409


async def test_a_code_for_an_unknown_bot_is_refused(world, keyring) -> None:
    keyring.add_credential("telegram", TelegramDetails(), SecretStr("123456:AAtelegram-1111"))

    response = await _ask_for_code(world, keyring, "no-such-bot", "telegram")

    assert response.status_code == 404
