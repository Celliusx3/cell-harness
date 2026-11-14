"""The chats' inbox: what every chat linked to a conversation queued, claimed and emptied."""

from __future__ import annotations

from harness.channels.repository.chat_repository import ChatState
from harness.channels.repository.json_chat_repository import JsonChatRepository
from harness.channels.service.inbox import ChatInbox
from harness.files import ChatFile
from harness.runtime.inbox import WaitingMessages
from tests.unit.helpers import no_skills


def a_file(name: str) -> ChatFile:
    return ChatFile(path=f"/files/{name}", name=name, media_type="text/plain", size=1)


async def test_every_linked_chat_is_claimed_in_a_stable_order_and_emptied(tmp_path) -> None:
    chats = JsonChatRepository(tmp_path / "chats")
    await chats.save(
        ChatState(
            channel="web",
            chat_id="w",
            conversation_id="c",
            pending=("from the web",),
            pending_files=(a_file("b.txt"),),
        )
    )
    await chats.save(
        ChatState(
            channel="telegram",
            chat_id="t",
            conversation_id="c",
            pending=("one", "two"),
            pending_files=(a_file("a.txt"),),
        )
    )
    await chats.save(
        ChatState(channel="discord", chat_id="d", conversation_id="other", pending=("x",))
    )

    claimed = await ChatInbox(chats, no_skills()).claim("c")

    assert claimed == WaitingMessages(
        text="one\ntwo\nfrom the web", files=(a_file("a.txt"), a_file("b.txt"))
    )
    assert (await chats.load("telegram", "t")).pending == ()
    assert (await chats.load("web", "w")).pending_files == ()
    assert (await chats.load("discord", "d")).pending == ("x",)


async def test_nothing_queued_claims_nothing(tmp_path) -> None:
    chats = JsonChatRepository(tmp_path / "chats")
    await chats.save(ChatState(channel="telegram", chat_id="t", conversation_id="c"))

    assert await ChatInbox(chats, no_skills()).claim("c") is None


async def test_a_slash_that_names_no_skill_is_claimed_as_typed(tmp_path) -> None:
    chats = JsonChatRepository(tmp_path / "chats")
    await chats.save(
        ChatState(channel="telegram", chat_id="t", conversation_id="c", pending=("/gone now",))
    )

    claimed = await ChatInbox(chats, no_skills()).claim("c")

    assert claimed == WaitingMessages(text="/gone now", files=())
