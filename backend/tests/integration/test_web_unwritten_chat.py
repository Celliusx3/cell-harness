"""A built-in bot's chat nobody wrote in yet opens in the browser as an empty chat, never saved."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from harness.bots import ASSISTANT_ID, BUILDER_ID
from harness.runtime.service import MODE_WITHOUT_TOOLSET
from harness.session.repository.session_repository import SessionNotFoundError
from tests.integration.web_helpers import api, build, events_from, frame_names
from tests.unit.fakes import ScriptedClient

BUILT_INS = (ASSISTANT_ID, BUILDER_ID)


def _saved_chats(tmp_path: Path) -> list[str]:
    return sorted(path.name for path in (tmp_path / "sessions").glob("*.jsonl"))


@pytest.fixture
async def browser(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    """The app on a new data folder where no chat was written and the bots were never listed."""
    service, runs = build(tmp_path, ScriptedClient([]))
    for chat_id in BUILT_INS:
        with pytest.raises(SessionNotFoundError):
            await service.read(chat_id)
    async with api(tmp_path, service, runs) as client:
        yield client
    assert _saved_chats(tmp_path) == []


@pytest.mark.parametrize("chat_id", BUILT_INS)
async def test_an_unwritten_chat_reads_as_an_empty_chat(
    browser: httpx.AsyncClient, chat_id: str
) -> None:
    read = await browser.get(f"/api/conversations/{chat_id}")

    assert read.status_code == 200, read.text
    detail = read.json()
    assert (detail["id"], detail["events"], detail["next_cursor"]) == (chat_id, [], 0)
    assert detail["running"] is False
    assert detail["mode"] == MODE_WITHOUT_TOOLSET


@pytest.mark.parametrize("chat_id", BUILT_INS)
async def test_an_unwritten_chat_s_event_stream_ends_with_no_event(
    browser: httpx.AsyncClient, chat_id: str
) -> None:
    stream = await browser.get(f"/api/conversations/{chat_id}/events?after=0")

    assert stream.status_code == 200, stream.text
    assert events_from(stream.text) == []
    assert frame_names(stream.text) == ["end"]


@pytest.mark.parametrize("chat_id", BUILT_INS)
async def test_an_unwritten_chat_has_no_tickets(browser: httpx.AsyncClient, chat_id: str) -> None:
    listed = await browser.get(f"/api/tickets?bot_id={chat_id}")

    assert listed.status_code == 200, listed.text
    assert listed.json() == []


async def test_clearing_an_unwritten_chat_is_accepted(browser: httpx.AsyncClient) -> None:
    cleared = await browser.post(f"/api/conversations/{ASSISTANT_ID}/clear")

    assert cleared.status_code == 204, cleared.text


async def test_naming_the_mode_an_unwritten_chat_is_in_is_accepted(
    browser: httpx.AsyncClient,
) -> None:
    sent = await browser.post(
        f"/api/conversations/{ASSISTANT_ID}/messages",
        json={"prompt": f"/mode {MODE_WITHOUT_TOOLSET}"},
    )

    assert sent.status_code == 202, sent.text
    assert sent.json()["queued"] is False


async def test_an_unwritten_chat_has_nothing_to_compact(browser: httpx.AsyncClient) -> None:
    compacted = await browser.post(f"/api/conversations/{ASSISTANT_ID}/compact")

    assert compacted.status_code == 409, compacted.text
    assert compacted.json()["detail"] == "nothing to compact"
