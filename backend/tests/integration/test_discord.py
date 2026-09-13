"""The Discord channel wired into the app: present with a token, absent without.

The receive/deliver path is the gateway's and is covered end to end by
`test_telegram.py`; what is Discord's here is the wiring in `build_channels`.
"""

from __future__ import annotations

from harness.agent.loop import LoopAgent
from harness.config.settings import Settings
from harness.runs.store import RunStore
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.web.server import build_channels
from tests.unit.fakes import ScriptedClient


def _stores(tmp_path) -> tuple[SessionService, RunStore]:
    sessions = SessionService(JsonlSessionRepository(tmp_path / "sessions"))
    return sessions, RunStore(sessions, LoopAgent(name="t", model="m", client=ScriptedClient([])))


async def test_no_token_means_no_channel(tmp_path) -> None:
    """Both tokens passed explicitly empty, so the developer's real
    `config.local.json` cannot decide this test — see `test_telegram.py`."""
    sessions, runs = _stores(tmp_path)
    settings = Settings(telegram={"bot_token": ""}, discord={"bot_token": ""})

    assert build_channels(settings, sessions, runs)[0].channels == ["web"]


async def test_a_whitespace_token_is_not_a_token(tmp_path) -> None:
    sessions, runs = _stores(tmp_path)
    settings = Settings(telegram={"bot_token": ""}, discord={"bot_token": "  "})

    assert build_channels(settings, sessions, runs)[0].channels == ["web"]


async def test_a_token_builds_a_channel(tmp_path) -> None:
    sessions, runs = _stores(tmp_path)
    settings = Settings(telegram={"bot_token": ""}, discord={"bot_token": "abc"})

    built, _ = build_channels(settings, sessions, runs)

    assert built.channels == ["web", "discord"]
    await built.aclose()


async def test_both_bots_share_one_gateway(tmp_path) -> None:
    sessions, runs = _stores(tmp_path)
    settings = Settings(telegram={"bot_token": "123:abc"}, discord={"bot_token": "abc"})

    built, _ = build_channels(settings, sessions, runs)

    assert built.channels == ["web", "telegram", "discord"]
    await built.aclose()


def test_the_token_reads_from_settings() -> None:
    assert Settings(discord={"bot_token": "abc"}).discord.bot_token == "abc"
