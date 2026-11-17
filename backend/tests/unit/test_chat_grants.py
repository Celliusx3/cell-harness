"""A chat's grants as its workers read and write them: its own bot's, in its own log."""

from __future__ import annotations

from harness.runs.service.chat_grant_service import ChatGrantService
from harness.session.domain.models import ApprovalGrant, TurnStart
from harness.tools import NO_CHAT_GRANTS
from tests.unit.fakes import ScriptedClient
from tests.unit.helpers import durable_service, new_session, run_service


def test_a_grant_counts_for_the_bot_whose_turn_it_was_logged_in() -> None:
    session = new_session()
    for event in (
        TurnStart(turn=1, bot_id="r"),
        ApprovalGrant(turn=1, tool="fs__write"),
        TurnStart(turn=2, bot_id="w"),
        ApprovalGrant(turn=2, tool="web__get"),
    ):
        session.append(event)

    assert session.granted_tools("r") == {"fs__write"}
    assert session.granted_tools("w") == {"web__get"}
    assert session.speaker_granted_tools() == {"web__get"}


async def test_a_grant_written_in_one_chat_is_read_there_and_not_in_another(tmp_path) -> None:
    chats = durable_service(tmp_path)
    for chat_id, bot_id in (("chat-a", "a"), ("chat-b", "b")):
        chat = await chats.create(chat_id)
        chat.append(TurnStart(turn=0, bot_id=bot_id))
        await chats.flush(chat)
    grants = ChatGrantService(run_service(chats, ScriptedClient([])), chats)

    await grants.grant("chat-b", "computer__shell")

    assert await grants.granted_tools("chat-b", "b") == {"computer__shell"}
    assert await grants.granted_tools("chat-a", "a") == frozenset()
    assert await grants.granted_tools("chat-b", "a") == frozenset()


async def test_a_chat_never_written_holds_no_grant(tmp_path) -> None:
    chats = durable_service(tmp_path)
    grants = ChatGrantService(run_service(chats, ScriptedClient([])), chats)

    await grants.grant("nowhere", "computer__shell")

    assert await grants.granted_tools("nowhere", "a") == frozenset()


async def test_a_toolset_whose_sessions_are_their_chats_keeps_no_grant_elsewhere() -> None:
    await NO_CHAT_GRANTS.grant("chat-a", "computer__shell")

    assert await NO_CHAT_GRANTS.granted_tools("chat-a", "a") == frozenset()
