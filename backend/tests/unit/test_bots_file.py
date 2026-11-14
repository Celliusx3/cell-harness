"""What the bots file's own type says: who is active, and the file with a bot saved or archived."""

from __future__ import annotations

import pytest

from harness.bots import ASSISTANT_ID, BUILDER_ID, Bot, BotNotFound
from harness.bots.domain.models import BotsFile

ASSISTANT = Bot(id=ASSISTANT_ID, name="Assistant", instructions="Be kind.")
BUILDER = Bot(id=BUILDER_ID, name="Bot builder", instructions="Build bots.")
BUILT_INS = (ASSISTANT, BUILDER)
RESEARCHER = Bot(id="r1", name="Researcher", instructions="Find sources.")
WRITER = Bot(id="w1", name="Writer", instructions="Write it up.")


def test_a_built_in_that_is_not_stored_is_its_default() -> None:
    assert BotsFile().active_bots(BUILT_INS) == (ASSISTANT, BUILDER)


def test_a_stored_built_in_replaces_its_default() -> None:
    renamed = ASSISTANT.model_copy(update={"name": "Helper"})

    assert BotsFile(bots=(renamed,)).active_bots(BUILT_INS) == (renamed, BUILDER)


def test_an_archived_built_in_is_still_active() -> None:
    archived = BUILDER.model_copy(update={"archived": True})

    assert BotsFile(bots=(archived,)).active_bots(BUILT_INS) == (ASSISTANT, archived)


def test_an_archived_bot_that_is_not_built_in_is_left_out() -> None:
    archived = RESEARCHER.model_copy(update={"archived": True})

    assert BotsFile(bots=(archived, WRITER)).active_bots(BUILT_INS) == (ASSISTANT, BUILDER, WRITER)


def test_the_built_ins_come_first_in_their_own_order_then_the_others_as_stored() -> None:
    stored = BotsFile(bots=(WRITER, BUILDER, RESEARCHER, ASSISTANT))

    assert stored.active_bots(BUILT_INS) == (ASSISTANT, BUILDER, WRITER, RESEARCHER)


def test_listing_the_active_bots_leaves_the_file_as_it_was() -> None:
    stored = BotsFile(bots=(WRITER, RESEARCHER))

    stored.active_bots(BUILT_INS)

    assert stored == BotsFile(bots=(WRITER, RESEARCHER))


def test_a_saved_bot_replaces_the_stored_one_in_its_place() -> None:
    renamed = RESEARCHER.model_copy(update={"name": "Scout"})

    saved = BotsFile(bots=(WRITER, RESEARCHER)).with_saved_bots((renamed,))

    assert saved.bots == (WRITER, renamed)


def test_a_saved_bot_that_is_not_yet_stored_goes_first() -> None:
    saved = BotsFile(bots=(WRITER,)).with_saved_bots((ASSISTANT, RESEARCHER))

    assert saved.bots == (ASSISTANT, RESEARCHER, WRITER)


def test_saving_bots_replaces_and_adds_in_one_call() -> None:
    renamed = WRITER.model_copy(update={"name": "Editor"})

    saved = BotsFile(bots=(RESEARCHER, WRITER)).with_saved_bots((renamed, ASSISTANT))

    assert saved.bots == (ASSISTANT, RESEARCHER, renamed)


def test_saving_no_bots_gives_back_an_equal_file() -> None:
    stored = BotsFile(bots=(WRITER, RESEARCHER))

    assert stored.with_saved_bots(()) == stored


def test_saving_a_bot_leaves_the_original_file_as_it_was() -> None:
    stored = BotsFile(bots=(WRITER,))

    stored.with_saved_bots((RESEARCHER, WRITER.model_copy(update={"name": "Editor"})))

    assert stored == BotsFile(bots=(WRITER,))


def test_archiving_sets_the_flag_on_that_bot_and_leaves_the_others() -> None:
    archived = BotsFile(bots=(WRITER, RESEARCHER)).with_bot_archived("r1")

    assert archived.bots == (WRITER, RESEARCHER.model_copy(update={"archived": True}))


def test_restoring_clears_the_flag_on_that_bot() -> None:
    stored = BotsFile(bots=(WRITER.model_copy(update={"archived": True}), RESEARCHER))

    assert stored.with_bot_restored("w1").bots == (WRITER, RESEARCHER)


def test_archiving_a_bot_that_is_not_stored_is_refused() -> None:
    with pytest.raises(BotNotFound):
        BotsFile(bots=(WRITER,)).with_bot_archived("r1")


def test_archiving_leaves_the_original_file_as_it_was() -> None:
    stored = BotsFile(bots=(WRITER, RESEARCHER))

    stored.with_bot_archived("w1")

    assert stored == BotsFile(bots=(WRITER, RESEARCHER))
