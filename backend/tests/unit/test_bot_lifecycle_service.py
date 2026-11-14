"""A change a person makes to a bot is refused whole, or reaches its turns, chat and schedules."""

from __future__ import annotations

import pytest

from harness.bots import (
    ASSISTANT_ID,
    Bot,
    BotDraft,
    BotEdit,
    BuiltInBotError,
    UnsavedModelError,
)
from harness.bots.service.bot_lifecycle_service import BotLifecycleService
from harness.secrets import SecretNotFound
from harness.session.domain.models import ToolCallEvent
from harness.session.repository.session_repository import SessionNotFoundError
from harness.session.service.session_service import SessionService
from tests.bot_models import save_chat_of
from tests.unit.fakes import SteppedClient, calls_tool, hanging_tool
from tests.unit.helpers import durable_service, run_service, until
from tests.unit.schedule_helpers import START, Clock, schedules_in
from tests.webapp import MODEL_CREDENTIAL, a_model_saved_in, bots_in

UNSAVED_MODEL = "unsaved_model"
HOURLY = "DTSTART:20261112T060100Z\nRRULE:FREQ=HOURLY"


@pytest.fixture
def sessions(tmp_path) -> SessionService:
    return durable_service(tmp_path / "sessions")


@pytest.fixture
def changes(tmp_path, sessions) -> BotLifecycleService:
    bots = bots_in(tmp_path, sessions)
    runs = run_service(
        sessions, SteppedClient(calls_tool("hang", '{"value": "x"}')), hanging_tool(), bots=bots
    )
    return BotLifecycleService(
        bots, runs, a_model_saved_in(tmp_path), schedules_in(tmp_path, Clock(START))
    )


async def a_bot(changes: BotLifecycleService) -> Bot:
    return await changes.create(
        BotDraft(name="Researcher", instructions="You find sources.", model=MODEL_CREDENTIAL)
    )


async def start_a_turn_in_the_chat_of(
    bot_id: str, changes: BotLifecycleService, sessions: SessionService
) -> None:
    session = await sessions.resume(changes.bots.chat_of(bot_id))
    changes.runs.start(session, "go")
    await until(
        lambda: any(isinstance(e, ToolCallEvent) for e in session.events()),
        what="the tool to be dispatched",
    )


async def test_creating_a_bot_on_a_model_that_is_not_saved_is_refused_and_makes_no_bot(
    changes,
) -> None:
    before = changes.bots.active_bots()
    draft = BotDraft(name="Researcher", instructions="You find sources.", model=UNSAVED_MODEL)

    with pytest.raises(UnsavedModelError) as refusal:
        await changes.create(draft)

    assert str(refusal.value) == changes.secrets.not_a_model_reason(UNSAVED_MODEL)
    assert changes.bots.active_bots() == before


async def test_editing_a_bot_onto_a_model_that_is_not_saved_is_refused_and_changes_nothing(
    changes,
) -> None:
    bot = await a_bot(changes)
    edit = BotEdit(name="Renamed", instructions="Changed.", model=UNSAVED_MODEL, max_workers=2)

    with pytest.raises(UnsavedModelError) as refusal:
        changes.update(bot.id, edit)

    assert str(refusal.value) == changes.secrets.not_a_model_reason(UNSAVED_MODEL)
    assert changes.bots.active_bot(bot.id) == bot


async def test_editing_a_bot_to_no_model_is_saved(changes) -> None:
    bot = await a_bot(changes)
    edit = BotEdit(name=bot.name, instructions=bot.instructions, model=None, max_workers=2)

    edited = changes.update(bot.id, edit)

    assert edited.model_credential is None
    assert changes.bots.active_bot(bot.id) == edited


async def test_a_key_that_is_not_saved_is_refused_and_the_bots_keys_are_unchanged(changes) -> None:
    bot = await a_bot(changes)

    with pytest.raises(SecretNotFound) as refusal:
        changes.set_allowed_secrets(bot.id, ("GITHUB_TOKEN",))

    assert str(refusal.value) == str(SecretNotFound("GITHUB_TOKEN"))
    assert changes.bots.active_bot(bot.id).secret_names == bot.secret_names


async def test_archiving_a_bot_stops_the_turn_running_in_its_chat(changes, sessions) -> None:
    bot = await a_bot(changes)
    await start_a_turn_in_the_chat_of(bot.id, changes, sessions)

    await changes.archive(bot.id)

    assert changes.runs.active_run(bot.id) is None
    assert [archived.id for archived in changes.bots.archived_bots()] == [bot.id]


async def test_deleting_a_bot_deletes_its_schedules_and_its_chat(changes, sessions) -> None:
    bot = await a_bot(changes)
    kept = changes.schedules.create(ASSISTANT_ID, "Check in", "Check in.", HOURLY)
    changes.schedules.create(bot.id, "Check in", "Check in.", HOURLY)

    await changes.delete(bot.id)

    assert changes.schedules.schedules() == (kept,)
    assert changes.bots.archived_bots() == ()
    with pytest.raises(SessionNotFoundError):
        await sessions.read(bot.id)


async def test_deleting_a_built_in_bot_is_refused_and_stops_nothing(changes, sessions) -> None:
    await save_chat_of(sessions, changes.bots, ASSISTANT_ID)
    await start_a_turn_in_the_chat_of(ASSISTANT_ID, changes, sessions)

    with pytest.raises(BuiltInBotError):
        await changes.delete(ASSISTANT_ID)

    running = changes.runs.active_run(ASSISTANT_ID)
    await changes.runs.aclose()
    assert running is not None
