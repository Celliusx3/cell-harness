"""The one place tests build a group service: over no groups file, or over one in a folder."""

from __future__ import annotations

from pathlib import Path

from harness.app_events import AppEventService
from harness.bots import BotService, GroupRepository, GroupService
from harness.session.service.session_service import SessionService

NO_GROUPS_FILE = Path("/nonexistent/cell-harness-groups.json")


def group_service(bots: BotService, sessions: SessionService) -> GroupService:
    """The chats of `bots` and no group, over a groups file that cannot exist; nobody listens."""
    return GroupService(bots, sessions, GroupRepository(NO_GROUPS_FILE), AppEventService())


def groups_in(
    tmp_path: Path, bots: BotService, sessions: SessionService, app_events: AppEventService
) -> GroupService:
    """Groups a test makes of `bots`, kept in `groups.json` under `tmp_path`."""
    return GroupService(bots, sessions, GroupRepository(tmp_path / "groups.json"), app_events)
