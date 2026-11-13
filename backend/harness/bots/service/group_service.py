"""Who answers in each chat: a bot's own chat holds it, a group's its members, in turn."""

from __future__ import annotations

from harness.bots.domain.models import Bot, BotNotFound, ChatMembers, Group, GroupDraft, GroupEmpty
from harness.bots.domain.turn_order import TurnOrder
from harness.bots.service.bot_service import BotService, bot_instructions_event
from harness.session.domain.log import Session
from harness.session.domain.models import GroupMembersEvent
from harness.session.service.session_service import SessionService


class GroupService:
    """Every group, the members of each chat, and which of them speaks next."""

    def __init__(self, bots: BotService, sessions: SessionService, turn_order: TurnOrder) -> None:
        self._bots = bots
        self._sessions = sessions
        self._turn_order = turn_order

    def groups(self) -> tuple[Group, ...]:
        """Every group, in the order each was made."""
        return self._bots.groups()

    async def create_group(self, draft: GroupDraft) -> Group:
        """A new group of active bots, its chat holding its members; `BotNotFound` for any other."""
        members = tuple(self._bots.active_bot(bot_id) for bot_id in draft.member_ids)
        session = await self._sessions.create()
        group = Group(id=session.id, name=draft.name, member_ids=draft.member_ids)
        session.append(_group_members_event(group, members))
        await self._sessions.flush(session)
        self._bots.add_group(group)
        return group

    def members_of_chat(self, chat_id: str) -> ChatMembers:
        """A bot's chat's bot, or a group's active members in order; `BotNotFound` for neither."""
        active = self._bots.active_bots_unopened()
        own = next((bot for bot in active if self._bots.chat_of(bot.id) == chat_id), None)
        if own is not None:
            return ChatMembers(group=None, bots=(own,))
        group = next((group for group in self._bots.groups() if group.id == chat_id), None)
        if group is None:
            raise BotNotFound(chat_id)
        by_id = {bot.id: bot for bot in active}
        return ChatMembers(
            group=group, bots=tuple(by_id[bot_id] for bot_id in group.member_ids if bot_id in by_id)
        )

    def asker(self, session: Session, call_id: str) -> Bot:
        """The member whose turn asked for `call_id`; the chat's only bot in an older log."""
        members = self.members_of_chat(session.id).bots
        bot_id = session.speaker_of_call(call_id)
        asking = members if bot_id is None else tuple(bot for bot in members if bot.id == bot_id)
        if len(asking) != 1:
            raise BotNotFound(bot_id if bot_id is not None else session.id)
        return asking[0]

    def first_speaker(self, session: Session, text: str) -> Bot:
        """Who answers `text` first, its instructions and group logged; `GroupEmpty` if none can."""
        members = self.members_of_chat(session.id)
        speakers = self._turn_order.first_speakers(text, members.bots)
        if not speakers:
            raise GroupEmpty(session.id)
        _log_speaker_if_changed(session, members, speakers[0])
        return speakers[0]

    def next_speaker(self, session: Session) -> Bot | None:
        """Who the queue says is next, its instructions and group logged; `None` when nobody is."""
        members = self.members_of_chat(session.id)
        speaker = self._turn_order.next_speaker(session.events(), members.bots)
        if speaker is None:
            return None
        _log_speaker_if_changed(session, members, speaker)
        return speaker


def _log_speaker_if_changed(session: Session, members: ChatMembers, bot: Bot) -> None:
    logged = session.bot_instructions(bot.id)
    if logged is None or (logged.name, logged.instructions) != (bot.name, bot.instructions):
        session.append(bot_instructions_event(bot))
    if members.group is not None:
        members_now = _group_members_event(members.group, members.bots)
        if session.group_members() != members_now:
            session.append(members_now)


def _group_members_event(group: Group, members: tuple[Bot, ...]) -> GroupMembersEvent:
    return GroupMembersEvent(name=group.name, members=tuple(bot.name for bot in members))
