"""Each bot's list of the saved keys it may use: added to, replaced, and forgotten."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.bots import ASSISTANT_ID, BUILDER_ID, BotDraft, BotNotFound, BotService
from tests.unit.helpers import durable_service


@pytest.fixture
def bots(tmp_path: Path) -> BotService:
    service = durable_service(tmp_path / "sessions")
    return BotService(tmp_path / "bots.json", service, assistant_instructions="Be kind.")


async def test_allowing_a_key_adds_it_once_and_keeps_the_bot_as_it_was(bots: BotService) -> None:
    made = await bots.create(BotDraft(name="Researcher", instructions="Cite."))

    bots.allow_secret(made.id, "github")
    allowed = bots.allow_secret(made.id, "github")

    assert allowed == made.model_copy(update={"secret_names": ("github",)})
    assert bots.active_bot(made.id) == allowed


async def test_allowing_assistant_a_key_stores_it_and_it_stays_first(bots: BotService) -> None:
    made = await bots.create(BotDraft(name="Researcher", instructions="Cite."))

    bots.allow_secret(ASSISTANT_ID, "github")

    listed = await bots.active_bots()
    assert [bot.id for bot in listed] == [ASSISTANT_ID, BUILDER_ID, made.id]
    assert listed[0].secret_names == ("github",)
    assert listed[0].instructions == "Be kind."


async def test_setting_a_bots_keys_replaces_the_list(bots: BotService) -> None:
    made = await bots.create(BotDraft(name="Researcher", instructions="Cite."))
    bots.allow_secret(made.id, "github")

    updated = bots.set_allowed_secrets(made.id, ("notion", "linear", "notion"))

    assert updated.secret_names == ("notion", "linear")
    assert bots.active_bot(made.id).secret_names == ("notion", "linear")
    assert bots.set_allowed_secrets(made.id, ()).secret_names == ()


async def test_a_bot_that_is_not_active_cannot_be_allowed_a_key(bots: BotService) -> None:
    made = await bots.create(BotDraft(name="Researcher", instructions="Cite."))
    bots.archive(made.id)

    with pytest.raises(BotNotFound):
        bots.allow_secret(made.id, "github")
    with pytest.raises(BotNotFound):
        bots.set_allowed_secrets("nope", ("github",))


async def test_forgetting_a_key_takes_it_off_every_bot_archived_ones_too(
    bots: BotService,
) -> None:
    first = await bots.create(BotDraft(name="First", instructions="One."))
    second = await bots.create(BotDraft(name="Second", instructions="Two."))
    bots.set_allowed_secrets(first.id, ("github", "notion"))
    bots.allow_secret(second.id, "github")
    bots.allow_secret(ASSISTANT_ID, "github")
    bots.archive(second.id)

    bots.forget_secret("github")

    assert bots.active_bot(first.id).secret_names == ("notion",)
    assert bots.active_bot(ASSISTANT_ID).secret_names == ()
    assert bots.archived_bots()[0].secret_names == ()


def test_forgetting_a_key_no_bot_holds_writes_nothing(tmp_path: Path, bots: BotService) -> None:
    bots.forget_secret("github")

    assert not (tmp_path / "bots.json").exists()


def test_a_bots_file_written_before_keys_reads_every_bot_as_allowed_none(
    tmp_path: Path, bots: BotService
) -> None:
    (tmp_path / "bots.json").write_text(
        json.dumps({"bots": [{"id": "r1", "name": "Researcher", "instructions": "Cite."}]})
    )

    assert bots.active_bot("r1").secret_names == ()
