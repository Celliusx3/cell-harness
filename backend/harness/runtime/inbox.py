"""What the person sent while a turn ran, read into that turn at its next step."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from harness.files import ChatFile
from harness.session.domain.log import Session

if TYPE_CHECKING:
    from harness.runtime.service import Runtime


@dataclass(frozen=True)
class WaitingMessages:
    """The messages a conversation's chats held, joined into one, and the files they carry."""

    text: str
    files: tuple[ChatFile, ...]


class Inbox(Protocol):
    """Where the messages sent to a conversation while its turn runs wait for that turn."""

    async def claim(self, conversation_id: str) -> WaitingMessages | None:
        """Return and remove what waits for `conversation_id`; `None` when nothing does."""
        ...


@dataclass(frozen=True)
class NoInbox:
    """The inbox of a runtime no chat writes to: nothing ever waits in it."""

    async def claim(self, conversation_id: str) -> WaitingMessages | None:
        """Nothing, for every conversation."""
        return None


NO_INBOX = NoInbox()


async def log_waiting_messages(
    runtime: Runtime, session: Session, *, turn: int, bot_id: str
) -> bool:
    """Log what waits for `session` as the person's message in `turn`: `True` when anything did."""
    sees_images = await runtime.can_see_images(bot_id)
    claimed = await runtime.inbox.claim(session.id)
    if claimed is None:
        return False
    runtime.log_person_message(
        session, claimed.text, claimed.files, turn=turn, sees_images=sees_images
    )
    return True
