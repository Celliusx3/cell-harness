"""Groups in the bots file: who is in one, and what a group may be made of."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from harness.bots import BotNotFound, BotService, ChatMembers, GroupDraft
from harness.llm.messages import ToolCall
from harness.session.models import (
    GroupMembersEvent,
    ToolCallEvent,
    TurnStart,
)
from harness.session.service import SessionService
from tests.unit.helpers import durable_service

ASK = ToolCall(id="c1", name="ask", arguments="{}")


@pytest.fixture
def service(tmp_path: Path) -> SessionService:
    return durable_service(tmp_path / "sessions")


@pytest.fixture
def bots(tmp_path: Path, service: SessionService) -> BotService:
    return BotService(tmp_path / "bots.json", service, assistant_instructions="Be kind.")


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
    bots: BotService, service: SessionService
) -> None:
    researcher = await bots.create("Researcher", "Cite.")
    writer = await bots.create("Writer", "Write.")

    group = await bots.create_group(
        GroupDraft(name=" Launch ", member_ids=(writer.id, researcher.id))
    )

    assert bots.groups() == (group,)
    assert group.name == "Launch"
    chat = await service.read(group.id)
    assert list(chat.events()) == [
        GroupMembersEvent(name="Launch", members=("Writer", "Researcher"))
    ]


async def test_a_group_takes_only_active_bots(bots: BotService) -> None:
    researcher = await bots.create("Researcher", "Cite.")
    writer = await bots.create("Writer", "Write.")
    bots.archive(writer.id)

    with pytest.raises(BotNotFound):
        await bots.create_group(GroupDraft(name="Launch", member_ids=(researcher.id, writer.id)))
    assert bots.groups() == ()


async def test_a_group_s_chat_is_answered_by_its_active_members_in_order(bots: BotService) -> None:
    researcher = await bots.create("Researcher", "Cite.")
    writer = await bots.create("Writer", "Write.")
    editor = await bots.create("Editor", "Edit.")
    group = await bots.create_group(
        GroupDraft(name="Launch", member_ids=(editor.id, researcher.id, writer.id))
    )

    bots.archive(researcher.id)
    await bots.delete(writer.id)

    assert bots.members_of_chat(group.id) == ChatMembers(group=group, bots=(editor,))


async def test_changing_a_bot_keeps_every_group(bots: BotService) -> None:
    researcher = await bots.create("Researcher", "Cite.")
    writer = await bots.create("Writer", "Write.")
    group = await bots.create_group(
        GroupDraft(name="Launch", member_ids=(researcher.id, writer.id))
    )

    bots.update(writer.id, "Writer", "Write shorter.")
    await bots.create("Editor", "Edit.")

    assert bots.groups() == (group,)


async def test_the_bot_that_asked_a_call_is_the_one_that_answers_it(
    bots: BotService, service: SessionService
) -> None:
    researcher = await bots.create("Researcher", "Cite.")
    writer = await bots.create("Writer", "Write.")
    group = await bots.create_group(
        GroupDraft(name="Launch", member_ids=(researcher.id, writer.id))
    )
    chat = await service.read(group.id)
    chat.append(TurnStart(turn=0, bot_id=writer.id))
    chat.append(ToolCallEvent(turn=0, step=0, call=ASK))

    assert bots.asker(chat, "c1") == writer


async def test_a_call_from_before_groups_is_answered_by_the_chat_s_only_bot(
    bots: BotService, service: SessionService
) -> None:
    researcher = await bots.create("Researcher", "Cite.")
    chat = await service.read(researcher.id)
    chat.append(TurnStart(turn=0))
    chat.append(ToolCallEvent(turn=0, step=0, call=ASK))

    assert bots.asker(chat, "c1") == researcher
