"""A heard message is answered by the bot named for it, and only by a member of the chat."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.app_events import AppEventService
from harness.bots import ASSISTANT_ID, BotDraft, BotRepository, BotService
from harness.groups import GroupDraft, NotAChatMemberError
from harness.session.domain.models import BotInstructionsEvent, GroupMembersEvent
from tests.unit.group_helpers import groups_in
from tests.unit.helpers import durable_service
from tests.webapp import MODEL_CREDENTIAL


async def _world(tmp_path: Path):
    sessions = durable_service(tmp_path / "sessions")
    bots = BotService(
        BotRepository(tmp_path / "bots.json"),
        sessions,
        assistant_instructions="Be kind.",
        app_events=AppEventService(),
    )
    groups = groups_in(tmp_path, bots, sessions, AppEventService())
    drafts = ("Researcher", "Writer")
    made = [
        await bots.create(BotDraft(name=name, instructions=f"{name}.", model=MODEL_CREDENTIAL))
        for name in drafts
    ]
    group = await groups.create(GroupDraft(name="Launch", member_ids=tuple(b.id for b in made)))
    return sessions, groups, group, made


async def test_the_named_member_speaks_with_its_instructions_logged(tmp_path: Path) -> None:
    sessions, groups, group, (_, writer) = await _world(tmp_path)
    session = await sessions.resume(group.id)

    speaker = groups.named_speaker(session, writer.id)

    assert speaker == writer
    events = session.events()
    assert [e.bot_id for e in events if isinstance(e, BotInstructionsEvent)] == [writer.id]
    assert sum(isinstance(e, GroupMembersEvent) for e in events) == 1


async def test_a_bot_outside_the_chat_cannot_be_named_to_speak(tmp_path: Path) -> None:
    sessions, groups, group, _ = await _world(tmp_path)
    session = await sessions.resume(group.id)

    with pytest.raises(NotAChatMemberError):
        groups.named_speaker(session, ASSISTANT_ID)
    assert not groups.is_member(group.id, ASSISTANT_ID)
