"""Deleting a bot deletes its workspace; a group's goes once no member is stored."""

from __future__ import annotations

from harness.app_events import AppEventService
from harness.bots import Bot, BotDraft
from harness.bots.service.bot_lifecycle_service import BotLifecycleService
from harness.groups import Group, GroupDraft, groups_left_without_members
from tests.unit.fakes import SteppedClient
from tests.unit.group_helpers import groups_in
from tests.unit.helpers import durable_service, run_service
from tests.unit.schedule_helpers import START, Clock, schedules_in
from tests.webapp import MODEL_CREDENTIAL, a_model_saved_in, bots_in, files_in


def test_a_group_is_left_without_members_only_when_none_of_them_is_stored() -> None:
    gone = Group(id="g1", name="Gone", member_ids=("a", "b"))
    half = Group(id="g2", name="Half", member_ids=("a", "c"))

    assert groups_left_without_members((gone, half), stored_bot_ids={"c"}) == (gone,)


def changes_in(tmp_path) -> BotLifecycleService:
    sessions = durable_service(tmp_path / "sessions")
    bots = bots_in(tmp_path, sessions)
    groups = groups_in(tmp_path, bots, sessions, AppEventService())
    runs = run_service(sessions, SteppedClient(), bots=bots, groups=groups)
    return BotLifecycleService(
        bots,
        runs,
        a_model_saved_in(tmp_path),
        schedules_in(tmp_path, Clock(START)),
        files_in(tmp_path),
    )


async def a_bot(changes: BotLifecycleService, name: str) -> Bot:
    draft = BotDraft(name=name, instructions="You help.", model=MODEL_CREDENTIAL)
    return await changes.create(draft)


async def test_deleting_members_deletes_their_workspaces_then_the_groups(tmp_path) -> None:
    changes = changes_in(tmp_path)
    writer, checker = await a_bot(changes, "Writer"), await a_bot(changes, "Checker")
    group = await changes.runs.groups.create(
        GroupDraft(name="Team", member_ids=(writer.id, checker.id))
    )
    workspaces = [changes.files.workspace(chat) for chat in (writer.id, checker.id, group.id)]
    writer_space, checker_space, group_space = workspaces

    await changes.delete(writer.id)

    assert not writer_space.exists()
    assert checker_space.exists() and group_space.exists()

    await changes.delete(checker.id)

    assert not checker_space.exists() and not group_space.exists()


async def test_archiving_a_bot_keeps_its_workspace_and_its_groups(tmp_path) -> None:
    changes = changes_in(tmp_path)
    writer, checker = await a_bot(changes, "Writer"), await a_bot(changes, "Checker")
    group = await changes.runs.groups.create(
        GroupDraft(name="Team", member_ids=(writer.id, checker.id))
    )
    writer_space, group_space = (
        changes.files.workspace(writer.id),
        changes.files.workspace(group.id),
    )

    await changes.archive(writer.id)
    await changes.delete(checker.id)

    assert writer_space.exists() and group_space.exists()
