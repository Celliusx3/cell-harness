"""Groups in the groups file: who is in one, and what a group may be made of."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from harness.app_events import AppEventService
from harness.bots import (
    ASSISTANT_ID,
    Bot,
    BotDraft,
    BotEdit,
    BotNotFound,
    BotRepository,
    BotService,
    ChatMembers,
    GroupDraft,
    GroupService,
)
from harness.llm import ToolCall
from harness.session.domain.models import (
    GroupMembersEvent,
    ToolCallEvent,
    TurnStart,
)
from harness.session.service.session_service import SessionService
from tests.unit.group_helpers import groups_in
from tests.unit.helpers import durable_service
from tests.webapp import MODEL_CREDENTIAL

ASK = ToolCall(id="c1", name="ask", arguments="{}")


@pytest.fixture
def service(tmp_path: Path) -> SessionService:
    return durable_service(tmp_path / "sessions")


@pytest.fixture
def bots(tmp_path: Path, service: SessionService) -> BotService:
    return BotService(
        BotRepository(tmp_path / "bots.json"),
        service,
        assistant_instructions="Be kind.",
        app_events=AppEventService(),
    )


@pytest.fixture
def groups(tmp_path: Path, bots: BotService, service: SessionService) -> GroupService:
    return groups_in(tmp_path, bots, service, AppEventService())


@pytest.mark.parametrize(
    "draft",
    [
        {"name": " ", "member_ids": ["a", "b"]},
        {"name": "Launch", "member_ids": ["a"]},
        {"name": "Launch", "member_ids": ["a", "a"]},
        {"name": "Launch", "member_ids": ["a", "b", "c", "d", "e", "f", "g"]},
    ],
)
def test_a_group_is_named_and_has_two_to_six_different_bots(draft: dict) -> None:
    with pytest.raises(ValidationError):
        GroupDraft.model_validate(draft)


async def test_a_group_s_chat_holds_its_members_from_the_start(
    groups: GroupService, bots: BotService, service: SessionService
) -> None:
    researcher = await bots.create(
        BotDraft(name="Researcher", instructions="Cite.", model=MODEL_CREDENTIAL)
    )
    writer = await bots.create(
        BotDraft(name="Writer", instructions="Write.", model=MODEL_CREDENTIAL)
    )

    group = await groups.create(GroupDraft(name=" Launch ", member_ids=(writer.id, researcher.id)))

    assert groups.groups() == (group,)
    assert group.name == "Launch"
    chat = await service.read(group.id)
    assert list(chat.events()) == [
        GroupMembersEvent(name="Launch", members=("Writer", "Researcher"))
    ]


async def test_a_group_takes_only_active_bots(groups: GroupService, bots: BotService) -> None:
    researcher = await bots.create(
        BotDraft(name="Researcher", instructions="Cite.", model=MODEL_CREDENTIAL)
    )
    writer = await bots.create(
        BotDraft(name="Writer", instructions="Write.", model=MODEL_CREDENTIAL)
    )
    bots.archive(writer.id)

    with pytest.raises(BotNotFound):
        await groups.create(GroupDraft(name="Launch", member_ids=(researcher.id, writer.id)))
    assert groups.groups() == ()


async def test_a_group_s_chat_is_answered_by_its_active_members_in_order(
    groups: GroupService, bots: BotService
) -> None:
    researcher = await bots.create(
        BotDraft(name="Researcher", instructions="Cite.", model=MODEL_CREDENTIAL)
    )
    writer = await bots.create(
        BotDraft(name="Writer", instructions="Write.", model=MODEL_CREDENTIAL)
    )
    editor = await bots.create(
        BotDraft(name="Editor", instructions="Edit.", model=MODEL_CREDENTIAL)
    )
    group = await groups.create(
        GroupDraft(name="Launch", member_ids=(editor.id, researcher.id, writer.id))
    )

    bots.archive(researcher.id)
    await bots.delete(writer.id)

    assert groups.chat_members(group.id) == ChatMembers(group=group, bots=(editor,))


async def test_changing_a_bot_keeps_every_group(groups: GroupService, bots: BotService) -> None:
    researcher = await bots.create(
        BotDraft(name="Researcher", instructions="Cite.", model=MODEL_CREDENTIAL)
    )
    writer = await bots.create(
        BotDraft(name="Writer", instructions="Write.", model=MODEL_CREDENTIAL)
    )
    group = await groups.create(GroupDraft(name="Launch", member_ids=(researcher.id, writer.id)))

    bots.update(
        writer.id,
        BotEdit(
            name="Writer",
            instructions="Write shorter.",
            model=MODEL_CREDENTIAL,
            max_workers=writer.max_workers,
        ),
    )
    await bots.create(BotDraft(name="Editor", instructions="Edit.", model=MODEL_CREDENTIAL))

    assert groups.groups() == (group,)


async def test_groups_left_in_the_bots_file_are_ignored_and_dropped_at_the_next_save(
    tmp_path: Path, groups: GroupService, bots: BotService
) -> None:
    researcher = Bot(id="r1", name="Researcher", instructions="Cite.")
    left_behind = {"id": "g1", "name": "Launch", "member_ids": ["r1", ASSISTANT_ID]}
    (tmp_path / "bots.json").write_text(
        json.dumps({"bots": [researcher.model_dump()], "groups": [left_behind]})
    )

    assert bots.active_bot("r1") == researcher
    assert groups.groups() == ()
    with pytest.raises(BotNotFound):
        groups.chat_members("g1")

    bots.archive("r1")

    assert set(json.loads((tmp_path / "bots.json").read_text())) == {"bots"}
    assert not (tmp_path / "groups.json").exists()


async def test_the_bot_that_asked_a_call_is_the_one_that_answers_it(
    groups: GroupService, bots: BotService, service: SessionService
) -> None:
    researcher = await bots.create(
        BotDraft(name="Researcher", instructions="Cite.", model=MODEL_CREDENTIAL)
    )
    writer = await bots.create(
        BotDraft(name="Writer", instructions="Write.", model=MODEL_CREDENTIAL)
    )
    group = await groups.create(GroupDraft(name="Launch", member_ids=(researcher.id, writer.id)))
    chat = await service.read(group.id)
    chat.append(TurnStart(turn=0, bot_id=writer.id))
    chat.append(ToolCallEvent(turn=0, step=0, call=ASK))

    assert groups.calling_bot(chat, "c1") == writer


async def test_a_call_from_before_groups_is_answered_by_the_chat_s_only_bot(
    groups: GroupService, bots: BotService, service: SessionService
) -> None:
    researcher = await bots.create(
        BotDraft(name="Researcher", instructions="Cite.", model=MODEL_CREDENTIAL)
    )
    chat = await service.read(researcher.id)
    chat.append(TurnStart(turn=0))
    chat.append(ToolCallEvent(turn=0, step=0, call=ASK))

    assert groups.calling_bot(chat, "c1") == researcher


async def test_a_chat_belongs_to_the_bot_whose_chat_it_is(
    groups: GroupService, bots: BotService
) -> None:
    made = await bots.create(
        BotDraft(name="Researcher", instructions="Cite.", model=MODEL_CREDENTIAL)
    )

    assert groups.chat_members("c0") == ChatMembers(group=None, bots=(made,))
    with pytest.raises(BotNotFound):
        groups.chat_members("c9")


async def test_a_bot_answers_in_the_chat_that_belongs_to_it(
    groups: GroupService, bots: BotService
) -> None:
    made = await bots.create(
        BotDraft(name="Researcher", instructions="Cite.", model=MODEL_CREDENTIAL)
    )

    assert groups.chat_members(bots.chat_of(made.id)).bots == (made,)
