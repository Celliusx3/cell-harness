"""The workspace a bot's turn in a chat is told of."""

from __future__ import annotations

from harness.files import ChatFileService
from harness.session.domain.models import WorkspaceEvent


def workspace_named(
    files: ChatFileService, bot_id: str, chat_id: str, own_chat_id: str | None
) -> WorkspaceEvent:
    """`chat_id`'s workspace for `bot_id`, with its own chat's when that is another folder."""
    workspace = str(files.workspace(chat_id))
    own = None if own_chat_id is None else str(files.workspace(own_chat_id))
    return WorkspaceEvent(
        bot_id=bot_id, workspace=workspace, own_workspace=None if own == workspace else own
    )
