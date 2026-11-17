"""The system message: the speaker's instructions and notes, the runtime's, servers'."""

from __future__ import annotations

from harness.prompts import GROUP_NOTE, GROUP_WORKSPACE_NOTE, WORKSPACE_NOTE
from harness.session.domain.log import Session
from harness.session.domain.models import GroupMembersEvent, WorkspaceEvent


def system_text(session: Session, guidance: str) -> str:
    """The speaker's prompt, its workspace, then each server's last logged instructions."""
    servers = (text for text in session.server_instructions().values() if text)
    workspace = _workspace_note(session.workspace_of(session.speaker_id()))
    parts = (_speaker_text(session, guidance), workspace, *servers)
    return "\n\n".join(part for part in parts if part)


def _workspace_note(named: WorkspaceEvent | None) -> str:
    """What the speaker is told of where it works; nothing when no workspace was logged."""
    if named is None:
        return ""
    if named.own_workspace is None:
        return WORKSPACE_NOTE.format(workspace=named.workspace)
    return GROUP_WORKSPACE_NOTE.format(workspace=named.workspace, own=named.own_workspace)


def _speaker_text(session: Session, guidance: str) -> str:
    """The speaker's last logged instructions, the group note in a group, then `guidance`."""
    logged = session.bot_instructions(session.speaker_id())
    if logged is None:
        return guidance
    group = session.group_members()
    note = "" if group is None else _group_note(group, logged.name)
    return " ".join(part for part in (logged.instructions, note, guidance) if part)


def _group_note(group: GroupMembersEvent, name: str) -> str:
    """What `name` is told about its group; nothing when no other member is left in it."""
    members = group.members
    at = members.index(name) if name in members else len(members)
    others = (*members[:at], *members[at + 1 :])
    if not others:
        return ""
    return GROUP_NOTE.format(name=name, group=group.name, others=_spoken_list(others))


def _spoken_list(names: tuple[str, ...]) -> str:
    """`A`, `A and B`, `A, B and C`."""
    if len(names) == 1:
        return names[0]
    return f"{', '.join(names[:-1])} and {names[-1]}"
