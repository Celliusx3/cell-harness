"""The grants a bot's chat holds, read and written for the workers it starts."""

from __future__ import annotations

from dataclasses import dataclass

from harness.runs.service.run_service import RunService
from harness.session.domain.models import ApprovalGrant
from harness.session.service.session_service import SessionService


@dataclass(frozen=True)
class ChatGrantService:
    """A chat's grants in its running turn's log, else in the stored one in `chats`."""

    runs: RunService
    chats: SessionService

    async def granted_tools(self, chat_id: str, bot_id: str) -> frozenset[str]:
        """The tools the person allowed `bot_id` to run unasked in `chat_id`, as logged now."""
        run = self.runs.active_run(chat_id)
        session = run.session if run is not None else await self.chats.read_or_empty(chat_id)
        return session.granted_tools(bot_id)

    async def grant(self, chat_id: str, tool: str) -> None:
        """Log in `chat_id`, in no turn, that `tool` runs unasked for the rest of it."""
        await self.runs.log_without_turn(chat_id, lambda turn: ApprovalGrant(turn=turn, tool=tool))
