"""`bot_create`: the New bot form's save, as a tool the model calls from chat."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import SecretStr

from harness.bots import BotService
from harness.secrets import SecretService
from harness.secrets.models.details import ModelDetails
from harness.tools import INVALID_ARGUMENTS, Failure, Ok
from harness.tools.native.bots import BOT_CREATE, bot_create_tool
from harness.web.runtime import DEFAULT_TOOLS, NOT_CALLABLE_FROM_SCRIPTS, SUBAGENT_TOOLS
from tests.unit.helpers import context_for, durable_service
from tests.webapp import MODEL_CREDENTIAL, secrets_in

CONFIG = Path(__file__).resolve().parents[2] / "config.json"


@pytest.fixture
def store(tmp_path: Path) -> BotService:
    return BotService(
        tmp_path / "bots.json", durable_service(tmp_path / "sessions"), assistant_instructions="A."
    )


@pytest.fixture
def keyring(tmp_path: Path) -> SecretService:
    secrets = secrets_in(tmp_path)
    details = ModelDetails(base_url="https://api.example.com/v1", model="m", vision=False)
    secrets.add_credential(MODEL_CREDENTIAL, details, SecretStr("sk-test-0000"))
    return secrets


async def call(store: BotService, keyring: SecretService, **arguments):
    tool = bot_create_tool(store, keyring)
    assert tool is not None
    return await tool.invoke(json.dumps(arguments), context=context_for())


async def test_a_bot_made_from_chat_is_the_one_the_form_makes(
    store: BotService, keyring: SecretService
) -> None:
    outcome = await call(
        store, keyring, name="Researcher", instructions="You find sources.", model=MODEL_CREDENTIAL
    )

    made = (await store.active_bots())[2]
    assert isinstance(outcome, Ok)
    assert (made.name, made.instructions) == ("Researcher", "You find sources.")
    assert made.model_credential == MODEL_CREDENTIAL
    assert made.id in outcome.text


@pytest.mark.parametrize(
    "arguments",
    [
        {"name": "  ", "instructions": "You find sources.", "model": MODEL_CREDENTIAL},
        {"name": "Researcher", "instructions": "You find sources."},
        {"name": "Researcher", "instructions": "You find sources.", "model": "nvidia"},
    ],
)
async def test_a_bot_with_a_blank_name_or_no_saved_model_is_not_made(
    store: BotService, keyring: SecretService, arguments: dict[str, str]
) -> None:
    outcome = await call(store, keyring, **arguments)

    assert isinstance(outcome, Failure)
    assert outcome.code == INVALID_ARGUMENTS
    assert [bot.name for bot in await store.active_bots()] == ["Assistant", "Bot builder"]


async def test_a_model_removed_since_the_tool_was_offered_is_refused(
    store: BotService, keyring: SecretService
) -> None:
    tool = bot_create_tool(store, keyring)
    assert tool is not None
    keyring.delete(MODEL_CREDENTIAL)
    arguments = {"name": "Researcher", "instructions": "Cite.", "model": MODEL_CREDENTIAL}

    outcome = await tool.invoke(json.dumps(arguments), context=context_for())

    assert isinstance(outcome, Failure)
    assert outcome.message == "'test_model' is not a saved LLM credential; none is saved"
    assert len(await store.active_bots()) == 2


def test_with_no_llm_credential_saved_there_is_no_tool(store: BotService, tmp_path: Path) -> None:
    assert bot_create_tool(store, secrets_in(tmp_path / "empty")) is None


def test_the_model_sees_a_name_instructions_and_the_saved_models(
    store: BotService, keyring: SecretService
) -> None:
    details = ModelDetails(base_url="https://other.example/v1", model="o", vision=False)
    keyring.add_credential("other_model", details, SecretStr("sk-other-0000"))
    tool = bot_create_tool(store, keyring)
    assert tool is not None

    assert tool.input_schema == {
        "description": "A new bot's name, instructions and model, from the API or a tool call.",
        "properties": {
            "name": {
                "description": "The name the sidebar shows, e.g. 'Researcher'.",
                "title": "Name",
                "type": "string",
            },
            "instructions": {
                "description": (
                    "What the bot is told before every turn in its chat, written to it as "
                    "'you', e.g. 'You find sources for a question and cite every claim.'"
                ),
                "title": "Instructions",
                "type": "string",
            },
            "model": {
                "description": "The saved LLM credential the bot answers on.",
                "enum": [MODEL_CREDENTIAL, "other_model"],
                "title": "Model",
                "type": "string",
            },
        },
        "required": ["name", "instructions", "model"],
        "title": "BotDraft",
        "type": "object",
    }


def test_one_saved_model_is_still_an_enum(store: BotService, keyring: SecretService) -> None:
    tool = bot_create_tool(store, keyring)
    assert tool is not None

    assert tool.input_schema["properties"]["model"]["enum"] == [MODEL_CREDENTIAL]
    assert "const" not in tool.input_schema["properties"]["model"]


def test_the_main_chat_is_offered_it_and_scripts_and_helpers_are_not() -> None:
    assert BOT_CREATE in DEFAULT_TOOLS
    assert BOT_CREATE in NOT_CALLABLE_FROM_SCRIPTS
    assert BOT_CREATE not in SUBAGENT_TOOLS


def test_the_committed_config_asks_before_a_bot_is_made() -> None:
    committed = json.loads(CONFIG.read_text())

    assert BOT_CREATE in committed["approval"]["tools"]
