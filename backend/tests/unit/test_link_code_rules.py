"""What voids a code, what lifts a silence, what a link moves, and what the route refuses."""

from __future__ import annotations

from pathlib import Path

import httpx
from fastapi import FastAPI

from harness.bots import ASSISTANT_ID
from harness.channels.links import LINK_CODE_SECONDS, WRONG_GUESSES_BEFORE_SILENCE, LinkCodes
from harness.channels.protocol import InboundMessage
from harness.channels.repository import ChatState
from harness.files import ChatFile
from harness.secrets import DiskSecretRepository, SecretService
from harness.web.routes.link_codes import build_router
from tests.unit.helpers import link_to_assistant
from tests.unit.link_helpers import World, world

PAGE = ChatFile(path="/f/c0/t1/page.png", name="page.png", media_type="image/png", size=8)


class Clock:
    """A clock the test moves by hand."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class Telegram:
    """A platform whose chats write nowhere until they are linked."""

    channel = "telegram"

    def conversation_for(self, chat_id: str) -> str:
        return ""

    async def run(self) -> None:
        raise AssertionError("never started")


def test_a_new_code_for_the_same_bot_voids_the_one_before() -> None:
    codes = LinkCodes(Clock())
    first = codes.issue("chef", "telegram")
    second = codes.issue("chef", "telegram")
    other = codes.issue("chef", "discord")

    assert codes.redeem("telegram", "1", first.code) is None
    assert codes.redeem("telegram", "1", second.code) == "chef"
    assert codes.redeem("discord", "1", other.code) == "chef"


def test_codes_for_two_bots_are_both_live_and_differ() -> None:
    codes = LinkCodes(Clock())
    chef = codes.issue("chef", "telegram")
    trader = codes.issue("trader", "telegram")

    assert chef.code != trader.code
    assert codes.redeem("telegram", "1", trader.code) == "trader"
    assert codes.redeem("telegram", "2", chef.code) == "chef"


def test_a_silenced_chat_may_guess_again_once_its_silence_ends() -> None:
    clock = Clock()
    codes = LinkCodes(clock)
    for _ in range(WRONG_GUESSES_BEFORE_SILENCE):
        codes.redeem("telegram", "1", "000000")
    clock.now += LINK_CODE_SECONDS - 1
    code = codes.issue("chef", "telegram")
    assert codes.redeem("telegram", "1", code.code) is None

    clock.now += 2

    assert codes.redeem("telegram", "1", code.code) == "chef"


def test_text_that_is_not_six_ascii_digits_is_no_guess() -> None:
    codes = LinkCodes(Clock())
    code = codes.issue("chef", "telegram")
    for text in ("hello", "12345", "1234567", "１２３４５６", "12 34 56", ""):
        assert codes.redeem("telegram", "1", text) is None

    assert codes.redeem("telegram", "1", code.code) == "chef"


async def test_an_archived_bots_code_links_nothing(tmp_path: Path) -> None:
    linked = await world(tmp_path)
    code = linked.codes.issue(linked.chef.id, "telegram")
    linked.bots.archive(linked.chef.id)

    assert await linked.links.link_if_code("telegram", "1", code.code) is None
    assert await linked.chats.load("telegram", "1") is None


async def test_moving_a_chat_to_another_bot_drops_its_queue(tmp_path: Path) -> None:
    linked = await world(tmp_path)
    queued = ChatState(
        channel="telegram",
        chat_id="1",
        conversation_id=linked.chef.id,
        linked_bot_id=linked.chef.id,
        pending=("for chef",),
        pending_files=(PAGE,),
        asked=("c9",),
    )
    await linked.chats.save(queued)
    code = linked.codes.issue(linked.trader.id, "telegram")

    await linked.links.link_if_code("telegram", "1", code.code)

    moved = await linked.chats.load("telegram", "1")
    assert moved == queued.model_copy(
        update={
            "conversation_id": linked.trader.id,
            "linked_bot_id": linked.trader.id,
            "pending": (),
            "pending_files": (),
        }
    )


async def test_a_chat_stored_before_codes_moving_to_a_bot_drops_its_queue(tmp_path: Path) -> None:
    linked = await world(tmp_path)
    queued = ChatState(
        channel="telegram", chat_id="1", conversation_id="an-old-chat", pending=("for you",)
    )
    await linked.chats.save(queued)
    code = linked.codes.issue(linked.chef.id, "telegram")

    await linked.links.link_if_code("telegram", "1", code.code)

    moved = await linked.chats.load("telegram", "1")
    assert (moved.linked_bot_id, moved.conversation_id) == (linked.chef.id, linked.chef.id)
    assert moved.pending == ()


async def test_a_code_for_the_bot_a_chat_is_on_keeps_its_queue(tmp_path: Path) -> None:
    linked = await world(tmp_path)
    queued = ChatState(
        channel="telegram",
        chat_id="1",
        conversation_id=linked.chef.id,
        linked_bot_id=linked.chef.id,
        pending=("still",),
    )
    await linked.chats.save(queued)
    code = linked.codes.issue(linked.chef.id, "telegram")

    assert await linked.links.link_if_code("telegram", "1", code.code) == linked.chef

    assert await linked.chats.load("telegram", "1") == queued


async def test_a_stored_chat_is_left_as_it_is_when_asked_to_store_it_on_assistant(
    tmp_path: Path,
) -> None:
    linked = await world(tmp_path)
    code = linked.codes.issue(linked.chef.id, "discord")
    await linked.links.link_if_code("discord", "1", code.code)
    before = await linked.chats.load("discord", "1")

    await linked.links.store_on_assistant_unless_stored("discord", "1")
    await linked.links.store_on_assistant_unless_stored("discord", "2")

    assert await linked.chats.load("discord", "1") == before
    stored = await linked.chats.load("discord", "2")
    assert (stored.conversation_id, stored.linked_bot_id) == (ASSISTANT_ID, None)


async def test_every_way_into_the_gateway_is_silent_for_an_unlinked_chat(tmp_path: Path) -> None:
    linked = await world(tmp_path)
    linked.gateway.register(Telegram())
    await link_to_assistant(linked.chats, "telegram", "2")

    assert (
        await linked.gateway.receive(InboundMessage(channel="telegram", chat_id="1", text="hi"))
        is None
    )
    assert await linked.gateway.is_linked("telegram", "1") is False
    assert await linked.gateway.stop("telegram", "1") is False
    assert await linked.gateway.compact_chat("telegram", "1") is None
    await linked.gateway.clear("telegram", "1")
    assert await linked.chats.load("telegram", "1") is None
    assert await linked.gateway.is_linked("telegram", "2") is True


async def _ask(linked: World, tmp_path: Path, bot_id: str, body: object) -> httpx.Response:
    keyring = SecretService(
        DiskSecretRepository(tmp_path / "secrets.json"), encryption_key="k" * 32
    )
    app = FastAPI()
    app.include_router(build_router(linked.codes, linked.bots, keyring))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as http:
        return await http.post(f"/api/bots/{bot_id}/link-codes", json=body)


async def test_a_code_for_an_archived_bot_is_refused(tmp_path: Path) -> None:
    linked = await world(tmp_path)
    linked.bots.archive(linked.chef.id)

    response = await _ask(linked, tmp_path, linked.chef.id, {"platform": "telegram"})

    assert response.status_code == 404


async def test_a_request_that_names_no_known_platform_is_refused(tmp_path: Path) -> None:
    linked = await world(tmp_path)

    for body in ({}, {"platform": "whatsapp"}, {"platform": "telegram", "extra": 1}, ["x"]):
        response = await _ask(linked, tmp_path, linked.chef.id, body)
        assert response.status_code == 422, body


async def test_the_refusal_for_a_platform_with_no_token_says_where_to_add_it(
    tmp_path: Path,
) -> None:
    linked = await world(tmp_path)

    response = await _ask(linked, tmp_path, linked.chef.id, {"platform": "discord"})

    assert response.status_code == 409
    assert "Credentials page" in response.json()["detail"]
    assert "Discord" in response.json()["detail"]
