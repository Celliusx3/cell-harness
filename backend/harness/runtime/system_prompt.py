"""The system message: the speaker's logged instructions, a group's note, the runtime's own."""

from __future__ import annotations

from harness.prompts import GROUP_NOTE
from harness.session.log import Session
from harness.session.models import GroupMembersEvent


def system_text(session: Session, guidance: str) -> str:
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
