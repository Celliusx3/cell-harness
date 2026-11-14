"""The runtime's inbox over the chats: what they queued during a turn, claimed by that turn."""

from __future__ import annotations

from harness.channels.repository.chat_repository import ChatRepository, ChatState
from harness.channels.service.turn_follower import QUEUE_SEPARATOR, expanded
from harness.runtime.inbox import Claimed
from harness.skills import SkillService


class ChatInbox:
    """Claims the messages every chat linked to a conversation queued, in a stable chat order."""

    def __init__(self, repository: ChatRepository, skills: SkillService) -> None:
        self._repository = repository
        self._skills = skills

    async def claim(self, conversation_id: str) -> Claimed | None:
        """Every linked chat's queue, joined as a drain joins it, and emptied; `None` if empty."""
        linked = await self._repository.chats_of(conversation_id)
        waiting = sorted((state for state in linked if state.pending), key=_chat_order)
        if not waiting:
            return None
        for state in waiting:
            await self._repository.save(
                state.model_copy(update={"pending": (), "pending_files": ()})
            )
        text = QUEUE_SEPARATOR.join(text for state in waiting for text in state.pending)
        files = tuple(file for state in waiting for file in state.pending_files)
        return Claimed(text=expanded(self._skills, text), files=files)


def _chat_order(state: ChatState) -> tuple[str, str]:
    return (state.channel, state.chat_id)
