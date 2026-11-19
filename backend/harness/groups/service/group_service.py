"""Who answers in each chat: a bot's own chat holds it, a group's its members, in turn."""

from __future__ import annotations

from harness.app_events import AppEventService, BotsChangedAppEvent
from harness.bots.domain.models import Bot, BotNotFound
from harness.bots.service.bot_service import BotService, bot_instructions_event
from harness.groups.domain.errors import (
    EmptyGroupError,
    GroupMemberNotFound,
    GroupNotFound,
    NotAChatMemberError,
)
from harness.groups.domain.models import ChatMembers, Group, GroupDraft, GroupEdit
from harness.groups.domain.speaker_queue import SpeakerQueue
from harness.groups.repository.group_repository import GroupRepository
from harness.session.domain.log import Session
from harness.session.domain.models import GroupMembersEvent
from harness.session.service.session_service import SessionService


class GroupService:
    """Every group, the members of each chat, and which of them speaks next."""

    def __init__(
        self,
        bots: BotService,
        sessions: SessionService,
        repository: GroupRepository,
        app_events: AppEventService,
    ) -> None:
        self._bots = bots
        self._sessions = sessions
        self._repository = repository
        self._app_events = app_events

    async def create(self, draft: GroupDraft) -> Group:
        """A new group of active bots, its chat holding its members; else `GroupMemberNotFound`."""
        members = tuple(self._active_member(bot_id) for bot_id in draft.member_ids)
        session = await self._sessions.create()
        group = Group(id=session.id, name=draft.name, member_ids=draft.member_ids)
        session.append(_group_members_event(group, members))
        await self._sessions.flush(session)
        self._repository.add(group)
        self._app_events.publish(BotsChangedAppEvent())
        return group

    def update(self, group_id: str, edit: GroupEdit) -> Group:
        """The group saved with `edit`; `GroupNotFound`, or `GroupMemberNotFound` for a lost bot."""
        if not any(group.id == group_id for group in self._repository.all()):
            raise GroupNotFound(group_id)
        for bot_id in edit.member_ids:
            self._active_member(bot_id)
        group = Group(id=group_id, name=edit.name, member_ids=edit.member_ids, lead_id=edit.lead_id)
        self._repository.update(group)
        self._app_events.publish(BotsChangedAppEvent())
        return group

    def all(self) -> tuple[Group, ...]:
        """Every group, in the order each was made."""
        return self._repository.all()

    def _active_member(self, bot_id: str) -> Bot:
        try:
            return self._bots.active_bot(bot_id)
        except BotNotFound as err:
            raise GroupMemberNotFound(bot_id) from err

    def chat_members(self, chat_id: str) -> ChatMembers:
        """A bot's chat's bot, or a group's active members in order; `BotNotFound` for neither."""
        active = self._bots.active_bots()
        own = next((bot for bot in active if self._bots.chat_of(bot.id) == chat_id), None)
        if own is not None:
            return ChatMembers(group=None, bots=(own,))
        stored = self._repository.all()
        group = next((group for group in stored if self.chat_of_group(group.id) == chat_id), None)
        if group is None:
            raise BotNotFound(chat_id)
        by_id = {bot.id: bot for bot in active}
        return ChatMembers(
            group=group, bots=tuple(by_id[bot_id] for bot_id in group.member_ids if bot_id in by_id)
        )

    def chat_of_group(self, group_id: str) -> str:
        """The id of the one chat the group talks in, which is the group's own id."""
        return group_id

    def calling_bot(self, session: Session, call_id: str) -> Bot:
        """The member whose turn asked for `call_id`; the chat's only bot in an older log."""
        members = self.chat_members(session.id).bots
        bot_id = session.calling_bot_id(call_id)
        matches = members if bot_id is None else tuple(bot for bot in members if bot.id == bot_id)
        if len(matches) != 1:
            raise BotNotFound(bot_id if bot_id is not None else session.id)
        return matches[0]

    def first_speaker(self, session: Session, text: str) -> Bot:
        """Who answers `text` first, its instructions and group logged; else `EmptyGroupError`."""
        members = self.chat_members(session.id)
        speakers = SpeakerQueue.after_message(text, members.bots).waiting
        if not speakers:
            raise EmptyGroupError(session.id)
        _log_speaker_and_members_if_changed(session, members, speakers[0])
        return speakers[0]

    def is_member(self, chat_id: str, bot_id: str) -> bool:
        """Whether `bot_id` is an active bot answering in `chat_id`; `BotNotFound` for no chat."""
        return any(bot.id == bot_id for bot in self.chat_members(chat_id).bots)

    def named_speaker(self, session: Session, bot_id: str) -> Bot:
        """`bot_id` to answer, its instructions and group logged; else `NotAChatMemberError`."""
        members = self.chat_members(session.id)
        speaker = next((bot for bot in members.bots if bot.id == bot_id), None)
        if speaker is None:
            raise NotAChatMemberError(session.id, bot_id)
        _log_speaker_and_members_if_changed(session, members, speaker)
        return speaker

    def next_speaker(self, session: Session) -> Bot | None:
        """Who the queue says is next, its instructions and group logged; `None` when nobody is."""
        members = self.chat_members(session.id)
        speaker = SpeakerQueue.next_in(session.events(), members.bots)
        if speaker is None:
            return None
        _log_speaker_and_members_if_changed(session, members, speaker)
        return speaker


def _log_speaker_and_members_if_changed(session: Session, members: ChatMembers, bot: Bot) -> None:
    logged = session.bot_instructions(bot.id)
    if logged is None or (logged.name, logged.instructions) != (bot.name, bot.instructions):
        session.append(bot_instructions_event(bot))
    if members.group is not None:
        members_now = _group_members_event(members.group, members.bots)
        if session.group_members() != members_now:
            session.append(members_now)


def _group_members_event(group: Group, members: tuple[Bot, ...]) -> GroupMembersEvent:
    return GroupMembersEvent(name=group.name, members=tuple(bot.name for bot in members))
