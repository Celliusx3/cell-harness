"""Each bot's turn asks its own model: its LLM credential, or none, and then it refuses."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from pydantic import SecretStr

from harness.app_events import AppEventService
from harness.bots import BotDraft, BotRepository, BotService
from harness.config.sections import LLMSettings
from harness.llm import AssistantMessage, LLMClient, StreamFailure, UserMessage
from harness.llm.adapters import OpenAISettings
from harness.runtime.models import PICK_A_MODEL, ModelChoice, NoModel
from harness.runtime.service import Runtime
from harness.secrets import DiskSecretRepository, SecretService
from harness.secrets.domain.details import ModelDetails
from harness.session.domain.compaction import CompactionEnd
from harness.session.domain.log import Session
from harness.session.domain.models import (
    AssistantChunk,
    AssistantMessageEvent,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)
from harness.web.model_choice import CredentialModels, ModelEndpoint
from tests.bot_models import put_on_model
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import drain, durable_service, new_session, no_images

KEY = "0123456789abcdef0123456789abcdef"
TRADER_URL = "https://api.trader.example/v1"
TRADER_KEY = "sk-trader-key-1234"
WINDOW = 8000
TRADER_MODEL = ModelDetails(base_url=TRADER_URL, model="big", vision=False)
BASE = LLMSettings(temperature=0.3, timeout_seconds=30)


@dataclass
class ChoicePerBot:
    """A model choice the test sets per bot; a bot it set none for has no model."""

    per_bot: dict[str, ModelChoice] = field(default_factory=dict)

    async def model_for(self, bot_id: str | None) -> ModelChoice | NoModel:
        choice = None if bot_id is None else self.per_bot.get(bot_id)
        return NoModel() if choice is None else choice


def _trader_client() -> tuple[ScriptedClient, ChoicePerBot]:
    trader = ScriptedClient(completed("trader"))
    return trader, ChoicePerBot({"trader": ModelChoice(trader, "big", False, None)})


async def _reply(runtime: Runtime, bot_id: str, tmp_path: Path) -> None:
    sessions = durable_service(tmp_path / f"sessions-{bot_id}")
    session = await sessions.create(bot_id)
    await drain(runtime.run("hi", session=session, bot_id=bot_id))


def _spoken_turn(session: Session, turn: int, bot_id: str | None) -> None:
    session.append(TurnStart(turn=turn, bot_id=bot_id))
    session.append(UserMessageEvent(turn=turn, message=UserMessage(content=f"q{turn}")))
    reply = AssistantMessage(content=f"a{turn}")
    session.append(AssistantMessageEvent(turn=turn, step=0, message=reply))
    session.append(TurnEnd(turn=turn, reason="completed"))


async def test_a_bot_with_its_own_model_is_answered_by_it(tmp_path: Path) -> None:
    trader, models = _trader_client()

    await _reply(Runtime(models=models, images=no_images()), "trader", tmp_path)

    assert trader.calls == 1


async def test_a_bot_with_no_model_asks_nothing_and_ends_with_the_line(tmp_path: Path) -> None:
    trader, models = _trader_client()
    sessions = durable_service(tmp_path / "sessions")
    session = await sessions.create("chef")

    await drain(
        Runtime(models=models, images=no_images()).run("hi", session=session, bot_id="chef")
    )

    chunks = [e.chunk for e in session.events() if isinstance(e, AssistantChunk)]
    assert trader.calls == 0
    assert chunks == [StreamFailure(reason=PICK_A_MODEL)]
    assert session.events()[-1] == TurnEnd(turn=0, reason="failed")


async def test_a_changed_choice_applies_to_the_next_turn(tmp_path: Path) -> None:
    first, second = ScriptedClient(completed("one")), ScriptedClient(completed("two"))
    models = ChoicePerBot({"trader": ModelChoice(first, "big", False, None)})
    runtime = Runtime(models=models, images=no_images())
    await _reply(runtime, "trader", tmp_path)

    models.per_bot["trader"] = ModelChoice(second, "bigger", False, None)
    await _reply(runtime, "trader", tmp_path / "again")

    assert (first.calls, second.calls) == (1, 1)


async def test_a_compaction_asks_the_model_of_the_bot_that_spoke_last() -> None:
    trader, models = _trader_client()
    session = new_session()
    _spoken_turn(session, 0, "chef")
    _spoken_turn(session, 1, "trader")

    await drain(Runtime(models=models, images=no_images()).compact(session=session))

    assert trader.calls == 1


@pytest.mark.parametrize("speaker", [None, "chef"])
async def test_a_compaction_with_no_model_ends_with_the_line(speaker: str | None) -> None:
    trader, models = _trader_client()
    session = new_session()
    _spoken_turn(session, 0, speaker)

    events = await drain(Runtime(models=models, images=no_images()).compact(session=session))

    assert trader.calls == 0
    assert events[-1] == CompactionEnd(turn=None, error=PICK_A_MODEL)


@dataclass
class ClientsMade:
    """A client factory that records the settings each client was made from."""

    made: list[tuple[OpenAISettings, LLMClient]] = field(default_factory=list)
    windows_asked: list[OpenAISettings] = field(default_factory=list)

    def __call__(self, settings: OpenAISettings) -> LLMClient:
        client = ScriptedClient(completed("ok"))
        self.made.append((settings, client))
        return client

    def window_for(self, settings: OpenAISettings) -> int:
        self.windows_asked.append(settings)
        return WINDOW

    def endpoint(self) -> ModelEndpoint:
        return ModelEndpoint(client_for=self, blocking_window_for=self.window_for)

    def settings_of(self, client: LLMClient) -> OpenAISettings:
        return next(settings for settings, made in self.made if made is client)

    def made_for(self, base_url: str) -> int:
        return sum(1 for settings, _ in self.made if settings.base_url == base_url)


@pytest.fixture
def keyring(tmp_path: Path) -> SecretService:
    return SecretService(DiskSecretRepository(tmp_path / "secrets.json"), encryption_key=KEY)


@pytest.fixture
def bots(tmp_path: Path) -> BotService:
    sessions = durable_service(tmp_path / "s")
    return BotService(
        BotRepository(tmp_path / "bots.json"),
        sessions,
        assistant_instructions="Be kind.",
        app_events=AppEventService(),
    )


async def _trader_on_its_model(keyring: SecretService, bots: BotService) -> str:
    keyring.add_credential("trader_model", TRADER_MODEL, SecretStr(TRADER_KEY))
    trader = await bots.create(BotDraft(name="Trader", instructions="Trade.", model="trader_model"))
    return trader.id


async def test_a_bot_on_a_credential_gets_its_endpoint_model_and_key(keyring, bots) -> None:
    trader_id = await _trader_on_its_model(keyring, bots)
    clients = ClientsMade()

    choice = await CredentialModels(keyring, bots, BASE, clients.endpoint()).model_for(trader_id)

    assert isinstance(choice, ModelChoice)
    made_from = clients.settings_of(choice.client)
    assert choice.model == "big"
    assert (made_from.base_url, made_from.model) == (TRADER_URL, "big")
    assert made_from.api_key == TRADER_KEY
    assert made_from.temperature == BASE.temperature
    assert made_from.timeout_seconds == BASE.timeout_seconds


async def test_a_bot_with_no_llm_credential_has_no_model(keyring, bots) -> None:
    await _trader_on_its_model(keyring, bots)
    chef = await bots.create(BotDraft(name="Chef", instructions="Cook.", model="trader_model"))
    put_on_model(bots, chef.id, None)
    clients = ClientsMade()

    choice = await CredentialModels(keyring, bots, BASE, clients.endpoint()).model_for(chef.id)

    assert choice == NoModel()
    assert clients.made == []


@pytest.mark.parametrize("bot_id", [None, "no-such-bot"])
async def test_no_bot_or_an_unknown_one_has_no_model(keyring, bots, bot_id) -> None:
    await _trader_on_its_model(keyring, bots)

    choice = await CredentialModels(keyring, bots, BASE, ClientsMade().endpoint()).model_for(bot_id)

    assert choice == NoModel()


async def test_clearing_a_bots_model_leaves_its_next_turn_with_no_model(keyring, bots) -> None:
    trader_id = await _trader_on_its_model(keyring, bots)
    models = CredentialModels(keyring, bots, BASE, ClientsMade().endpoint())
    await models.model_for(trader_id)

    put_on_model(bots, trader_id, None)

    assert await models.model_for(trader_id) == NoModel()


async def test_removing_a_bots_credential_leaves_it_with_no_model(keyring, bots) -> None:
    trader_id = await _trader_on_its_model(keyring, bots)
    models = CredentialModels(keyring, bots, BASE, ClientsMade().endpoint())
    await models.model_for(trader_id)

    keyring.delete("trader_model")

    assert await models.model_for(trader_id) == NoModel()


async def test_the_key_is_unsealed_once_until_the_credential_changes(keyring, bots) -> None:
    trader_id = await _trader_on_its_model(keyring, bots)
    clients = ClientsMade()
    models = CredentialModels(keyring, bots, BASE, clients.endpoint())

    await models.model_for(trader_id)
    await models.model_for(trader_id)
    changed_details = TRADER_MODEL.model_copy(update={"model": "bigger"})
    keyring.change_credential("trader_model", changed_details, None)
    changed = await models.model_for(trader_id)

    assert clients.made_for(TRADER_URL) == 2
    assert [asked.model for asked in clients.windows_asked] == ["big", "bigger"]
    assert isinstance(changed, ModelChoice)
    assert changed.model == "bigger"
    assert changed.context_tokens == WINDOW
