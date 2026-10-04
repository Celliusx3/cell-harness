"""`bot_create`: the New bot form's save, as a tool the model calls from chat."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.bots import BotStore
from harness.tools.definition import INVALID_ARGUMENTS, Failure, Ok
from harness.tools.native.bots import BOT_CREATE, bot_create_tool
from harness.web.agent import DEFAULT_TOOLS, NOT_CALLABLE_FROM_SCRIPTS, SUBAGENT_TOOLS
from tests.unit.helpers import context_for, durable_service

CONFIG = Path(__file__).resolve().parents[2] / "config.json"


@pytest.fixture
def store(tmp_path: Path) -> BotStore:
    return BotStore(
        tmp_path / "bots.json", durable_service(tmp_path / "sessions"), assistant_instructions="A."
    )


async def call(store: BotStore, **arguments):
    return await bot_create_tool(store).invoke(json.dumps(arguments), context=context_for())


async def test_a_bot_made_from_chat_is_the_one_the_form_makes(store: BotStore) -> None:
    outcome = await call(store, name="Researcher", instructions="You find sources.")

    made = (await store.list())[1]
    assert isinstance(outcome, Ok)
    assert (made.name, made.instructions) == ("Researcher", "You find sources.")
    assert made.id in outcome.text


async def test_a_blank_name_is_refused_as_the_form_refuses_it(store: BotStore) -> None:
    outcome = await call(store, name="  ", instructions="You find sources.")

    assert isinstance(outcome, Failure)
    assert outcome.code == INVALID_ARGUMENTS
    assert [bot.name for bot in await store.list()] == ["Assistant"]


def test_the_main_chat_is_offered_it_and_scripts_and_helpers_are_not() -> None:
    assert BOT_CREATE in DEFAULT_TOOLS
    assert BOT_CREATE in NOT_CALLABLE_FROM_SCRIPTS
    assert BOT_CREATE not in SUBAGENT_TOOLS


def test_the_committed_config_asks_before_a_bot_is_made() -> None:
    committed = json.loads(CONFIG.read_text())

    assert BOT_CREATE in committed["approval"]["tools"]
