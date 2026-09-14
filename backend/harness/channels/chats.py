"""Which conversation a chat is on.

A chat is an address — Telegram chat `4242`, Discord channel `123`, a browser
tab — and a conversation is a transcript on disk. One address is on many
transcripts over its life (`/new` moves it), so `ChatState` is the pointer from
the one to the other. `state_of` reads the pointer; `session_for` follows it,
creating a transcript when the chat has none.

What a *missing* transcript means is read off the channel rather than branched
on by name: a chat must recover, an API must 404 — that is `on_missing`, and
these two functions are its only readers.
"""

from __future__ import annotations

import logging

from harness.channels.protocol import Channel
from harness.channels.repository import ChatRepository, ChatState
from harness.session.log import Session
from harness.session.repository import SessionNotFoundError
from harness.session.service import SessionService

logger = logging.getLogger("harness.channels")


async def state_of(repository: ChatRepository, channel: Channel, chat_id: str) -> ChatState:
    """This chat's state, defaulted for one we have not seen.

    Not persisted here, so a chat that only ever sent `/stop` leaves nothing
    behind. Whoever changes something saves it.
    """
    stored = await repository.load(channel.channel, chat_id)
    if stored is not None:
        return stored
    if channel.on_missing == "raise":
        # **A client channel's chat id *is* a conversation id.** It has no
        # stored mapping for a conversation it has not written to before, and
        # it must not invent one — so the id it was given is the answer, and
        # `resume` decides later whether it names anything.
        #
        # This is what lets the browser reply to a conversation that started
        # on Telegram: there is no `("web", c0)` mapping, but `c0` is a real
        # conversation and that is all a browser needs to know.
        #
        # Resolved *here* rather than at the point of use, so `receive`'s busy
        # check sees the conversation id too. It did not, briefly, and the
        # consequence was severe: the check fell through, `resume` ran against
        # a turn already executing, and crash repair committed a synthetic
        # result for a tool call still in flight.
        return ChatState(channel=channel.channel, chat_id=chat_id, conversation_id=chat_id)
    return ChatState(channel=channel.channel, chat_id=chat_id)


async def session_for(
    repository: ChatRepository, sessions: SessionService, channel: Channel, state: ChatState
) -> tuple[ChatState, Session]:
    """The session this chat's next turn runs in, and the state that names it —
    stored, so a message arriving mid-turn has a `pending` to go into."""
    if state.conversation_id:
        try:
            session = await sessions.resume(state.conversation_id)
        except SessionNotFoundError:
            if channel.on_missing == "raise":
                # A client that named an id is asking about *that* id, so the
                # honest answer is that it does not exist. Recreating here
                # would turn a mistyped URL into a new conversation.
                raise
            # Reachable: `/stop` a first message before the loop's first
            # checkpoint and the run is cancelled having appended nothing, so
            # lazy materialization leaves no file while the chat already
            # points at the id. Without this a *chat* is permanently broken —
            # every later message resumes an id that will never exist, and the
            # person holding the phone has no way to fix it. Dropping it costs
            # nothing; the conversation is empty by definition.
            logger.info(
                "%s chat %s pointed at unwritten conversation %s; starting fresh",
                state.channel,
                state.chat_id,
                state.conversation_id,
            )
            session = await sessions.create()
            state = state.model_copy(update={"conversation_id": session.id, "delivered_through": 0})
            await repository.save(state)
    else:
        # First message here, or the first after `/new`. Created now rather
        # than at first contact so the id always names a conversation that
        # will actually exist.
        session = await sessions.create()
        state = state.model_copy(update={"conversation_id": session.id})
        await repository.save(state)

    if not await repository.load(state.channel, state.chat_id):
        # First time we have seen this chat, including a client channel that
        # resolved its conversation by id above. Stored now so a message
        # arriving mid-turn has a `pending` to go into.
        await repository.save(state)
    return state, session
