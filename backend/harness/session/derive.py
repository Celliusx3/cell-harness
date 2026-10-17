"""Project model history from the log, as the bot that opened its last turn should see it."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass

from harness.llm.messages import Block, Message, Text, ToolMessage, UserMessage
from harness.prompts import (
    ATTACHED_FILE,
    BOT_MESSAGE_REQUEST,
    BOT_MESSAGE_RESULT,
    CUT_NOTE,
    NO_RESPONSE,
    PRUNED,
    SPEAKER_TAG,
)
from harness.session.compaction import boundary, pruned_ids
from harness.session.models import (
    ApplicationMessageEvent,
    AssistantMessageEvent,
    BotInstructionsEvent,
    BotMessage,
    BotMessageEvent,
    BotMessageIntent,
    SessionEvent,
    ToolResultEvent,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)
from harness.session.speakers import last_speaker, turn_speakers

RESULT_LIMIT = 12_000

BOT_MESSAGE_TEMPLATES: Mapping[BotMessageIntent, str] = {
    "request": BOT_MESSAGE_REQUEST,
    "result": BOT_MESSAGE_RESULT,
}


@dataclass(frozen=True)
class Voices:
    """Which bot opened each turn, what each bot is called, and the bot the history is for."""

    speakers: Mapping[int, str]
    names: Mapping[str, str]
    listener: str | None

    def other_speaker(self, turn: int) -> str | None:
        """The name, or else the id, of the bot that opened `turn` when it is not the listener."""
        bot_id = self.speakers.get(turn)
        if bot_id is None or bot_id == self.listener:
            return None
        return self.names.get(bot_id, bot_id)


def derive_messages(events: Iterable[SessionEvent]) -> list[Message]:
    """The conversation as the bot that opened its last turn should see it."""
    log = tuple(events)
    voices = Voices(turn_speakers(log), _bot_names(log), last_speaker(log))
    pruned = pruned_ids(log)
    messages: list[Message] = []
    start = boundary(log)
    if start is not None:
        summary = log[start]
        assert summary.message is not None
        messages.append(UserMessage(content=summary.message.content))
        log = log[start + 1 :]
    messages.extend(_as_heard(log, voices, pruned))
    return messages


def _as_heard(
    tail: Sequence[SessionEvent], voices: Voices, pruned: frozenset[str]
) -> Iterator[Message]:
    """Every event as the listener's own, but another bot's turn only as what it said, tagged."""
    heard: tuple[str, ...] = ()
    speaker = ""
    for event in tail:
        if isinstance(event, (TurnStart, TurnEnd)) and heard:
            yield _speaker_message(speaker, heard)
            heard = ()
        if isinstance(event, UserMessageEvent):
            yield _person_message(event)
        elif isinstance(event, BotMessageEvent):
            yield _bot_message(event.message)
        elif isinstance(event, (ApplicationMessageEvent, AssistantMessageEvent, ToolResultEvent)):
            other = voices.other_speaker(event.turn)
            if other is None:
                yield _own_message(event, pruned)
            elif isinstance(event, AssistantMessageEvent) and _is_said(event.message.content):
                speaker, heard = other, (*heard, event.message.content.strip())
    if heard:
        yield _speaker_message(speaker, heard)


def _own_message(
    event: ApplicationMessageEvent | AssistantMessageEvent | ToolResultEvent, pruned: frozenset[str]
) -> Message:
    if isinstance(event, ApplicationMessageEvent):
        return UserMessage(content=event.message.content)
    if isinstance(event, AssistantMessageEvent):
        return event.message
    if event.message.tool_call_id in pruned:
        return ToolMessage(tool_call_id=event.message.tool_call_id, content=PRUNED)
    return _limited(event.message)


def _person_message(event: UserMessageEvent) -> UserMessage:
    """The person's text, then a line for each file they attached; the text alone without one."""
    if not event.files:
        return event.message
    lines = "\n".join(
        ATTACHED_FILE.format(
            name=file.name, media_type=file.media_type, size=file.size, path=file.path
        )
        for file in event.files
    )
    return UserMessage(content=f"{event.message.content}\n\n{lines}")


def _bot_message(message: BotMessage) -> UserMessage:
    """Another bot's message as the listener hears it, worded for why it was sent."""
    template = BOT_MESSAGE_TEMPLATES[message.intent]
    return UserMessage(content=template.format(name=message.from_name, text=message.text))


def _is_said(text: str) -> bool:
    """Whether a reply has something in it for the others to read."""
    stripped = text.strip()
    return bool(stripped) and stripped != NO_RESPONSE


def _speaker_message(name: str, said: tuple[str, ...]) -> UserMessage:
    return UserMessage(content=SPEAKER_TAG.format(name=name, text="\n\n".join(said)))


def _bot_names(events: Sequence[SessionEvent]) -> Mapping[str, str]:
    """Each bot's name as the last instructions logged for it give it."""
    return {
        event.bot_id: event.name
        for event in events
        if isinstance(event, BotInstructionsEvent) and event.bot_id is not None
    }


def _limited(message: ToolMessage) -> ToolMessage:
    total = sum(len(block.text) for block in message.content if isinstance(block, Text))
    if total <= RESULT_LIMIT:
        return message
    note = CUT_NOTE.format(total=total, limit=RESULT_LIMIT)
    return ToolMessage(
        tool_call_id=message.tool_call_id, content=tuple(_cut_blocks(message.content, note))
    )


def _cut_blocks(blocks: tuple[Block, ...], note: str) -> Iterator[Block]:
    start = 0
    for block in blocks:
        if not isinstance(block, Text):
            yield block
            continue
        end = start + len(block.text)
        if end <= RESULT_LIMIT:
            yield block
        elif start <= RESULT_LIMIT:
            yield Text(text=block.text[: RESULT_LIMIT - start] + note)
        start = end
