"""Each bot's turn asks its own model: its LLM credential, or the Default model when it has none."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from pydantic import SecretStr

from harness.bots import BotDraft, BotService
from harness.config.sections import LLMSettings
from harness.llm import AssistantMessage, LLMClient, UserMessage
from harness.runtime.models import ModelChoice
from harness.runtime.service import Runtime
from harness.secrets import DiskSecretRepository, SecretService
from harness.secrets.models.details import ModelDetails
from harness.session.log import Session
from harness.session.models import AssistantMessageEvent, TurnEnd, TurnStart, UserMessageEvent
from harness.web.bot_models import CredentialModels
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import drain, durable_service, new_session

KEY = "0123456789abcdef0123456789abcdef"
TRADER_URL = "https://api.trader.example/v1"
TRADER_KEY = "sk-trader-key-1234"
TRADER_MODEL = ModelDetails(base_url=TRADER_URL, model="big")
DEFAULT = LLMSettings(
    api_key="sk-default-key-0000",
    model="small",
    vision=False,
    base_url="https://api.default.example/v1",
    temperature=0.3,
)


@dataclass
class ChoicePerBot:
    """A model choice the test sets per bot, falling back to one default."""

    default: ModelChoice
    per_bot: dict[str, ModelChoice] = field(default_factory=dict)

    async def model_for(self, bot_id: str | None) -> ModelChoice:
        return self.default if bot_id is None else self.per_bot.get(bot_id, self.default)


def _two_clients() -> tuple[ScriptedClient, ScriptedClient, ChoicePerBot]:
    default, trader = ScriptedClient(completed("default")), ScriptedClient(completed("trader"))
    models = ChoicePerBot(ModelChoice(default, "small"), {"trader": ModelChoice(trader, "big")})
    return default, trader, models


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
    default, trader, models = _two_clients()

    await _reply(Runtime(models=models, images=None), "trader", tmp_path)

    assert (trader.calls, default.calls) == (1, 0)


async def test_a_bot_without_one_is_answered_by_the_default(tmp_path: Path) -> None:
    default, trader, models = _two_clients()

    await _reply(Runtime(models=models, images=None), "chef", tmp_path)

    assert (trader.calls, default.calls) == (0, 1)


async def test_a_changed_choice_applies_to_the_next_turn(tmp_path: Path) -> None:
    first, second = ScriptedClient(completed("one")), ScriptedClient(completed("two"))
    default = ModelChoice(ScriptedClient(completed("d")), "small")
    models = ChoicePerBot(default, {"trader": ModelChoice(first, "big")})
    runtime = Runtime(models=models, images=None)
    await _reply(runtime, "trader", tmp_path)

    models.per_bot["trader"] = ModelChoice(second, "bigger")
    await _reply(runtime, "trader", tmp_path / "again")

    assert (first.calls, second.calls) == (1, 1)


async def test_a_compaction_asks_the_model_of_the_bot_that_spoke_last() -> None:
    default, trader, models = _two_clients()
    session = new_session()
    _spoken_turn(session, 0, "chef")
    _spoken_turn(session, 1, "trader")

    await drain(Runtime(models=models, images=None).compact(session=session))

    assert (trader.calls, default.calls) == (1, 0)


async def test_a_chat_logged_before_bots_is_compacted_by_the_default() -> None:
    default, trader, models = _two_clients()
    session = new_session()
    _spoken_turn(session, 0, None)

    await drain(Runtime(models=models, images=None).compact(session=session))

    assert (trader.calls, default.calls) == (0, 1)


@dataclass
class ClientsMade:
    """A client factory that records the settings each client was made from."""

    made: list[tuple[LLMSettings, LLMClient]] = field(default_factory=list)

    def __call__(self, settings: LLMSettings) -> LLMClient:
        client = ScriptedClient(completed("ok"))
        self.made.append((settings, client))
        return client

    def settings_of(self, client: LLMClient) -> LLMSettings:
        return next(settings for settings, made in self.made if made is client)

    def made_for(self, base_url: str) -> int:
        return sum(1 for settings, _ in self.made if settings.base_url == base_url)


@pytest.fixture
def keyring(tmp_path: Path) -> SecretService:
    return SecretService(DiskSecretRepository(tmp_path / "secrets.json"), encryption_key=KEY)


@pytest.fixture
def bots(tmp_path: Path) -> BotService:
    sessions = durable_service(tmp_path / "s")
    return BotService(tmp_path / "bots.json", sessions, assistant_instructions="Be kind.")


async def _trader_on_its_model(keyring: SecretService, bots: BotService) -> str:
    trader = await bots.create(BotDraft(name="Trader", instructions="Trade."))
    keyring.add_credential("trader_model", TRADER_MODEL, SecretStr(TRADER_KEY))
    bots.tie_credential("trader_model", "llm", (trader.id,))
    return trader.id


async def test_a_tied_bot_gets_its_credentials_endpoint_model_and_key(keyring, bots) -> None:
    trader_id = await _trader_on_its_model(keyring, bots)
    clients = ClientsMade()

    choice = await CredentialModels(keyring, bots, DEFAULT, clients).model_for(trader_id)

    made_from = clients.settings_of(choice.client)
    assert choice.model == "big"
    assert (made_from.base_url, made_from.model) == (TRADER_URL, "big")
    assert made_from.api_key == TRADER_KEY
    assert made_from.temperature == DEFAULT.temperature


async def test_a_bot_with_no_llm_credential_gets_the_default(keyring, bots) -> None:
    chef = await bots.create(BotDraft(name="Chef", instructions="Cook."))
    clients = ClientsMade()

    choice = await CredentialModels(keyring, bots, DEFAULT, clients).model_for(chef.id)

    assert choice.model == "small"
    assert clients.settings_of(choice.client).api_key == DEFAULT.api_key


@pytest.mark.parametrize("bot_id", [None, "no-such-bot"])
async def test_no_bot_or_an_unknown_one_gets_the_default(keyring, bots, bot_id) -> None:
    clients = ClientsMade()

    choice = await CredentialModels(keyring, bots, DEFAULT, clients).model_for(bot_id)

    assert clients.settings_of(choice.client).api_key == DEFAULT.api_key


async def test_untying_a_bot_hands_its_next_turn_to_the_default(keyring, bots) -> None:
    trader_id = await _trader_on_its_model(keyring, bots)
    models = CredentialModels(keyring, bots, DEFAULT, ClientsMade())
    await models.model_for(trader_id)

    bots.tie_credential("trader_model", "llm", ())

    assert (await models.model_for(trader_id)).model == "small"


async def test_the_key_is_unsealed_once_until_the_credential_changes(keyring, bots) -> None:
    trader_id = await _trader_on_its_model(keyring, bots)
    clients = ClientsMade()
    models = CredentialModels(keyring, bots, DEFAULT, clients)

    await models.model_for(trader_id)
    await models.model_for(trader_id)
    changed_details = TRADER_MODEL.model_copy(update={"model": "bigger"})
    keyring.change_credential("trader_model", changed_details, None)
    changed = await models.model_for(trader_id)

    assert clients.made_for(TRADER_URL) == 2
    assert changed.model == "bigger"
