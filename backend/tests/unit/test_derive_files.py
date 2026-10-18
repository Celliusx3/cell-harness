"""What the model reads of the files the person attached."""

from __future__ import annotations

from harness.files import ChatFile
from harness.llm import UserMessage
from harness.prompts import ATTACHED_FILE
from harness.session.derive import derive_messages
from harness.session.models import TurnStart, UserMessageEvent

PAGE = ChatFile(path="/f/assistant/t1/page.png", name="page.png", media_type="image/png", size=8)
NOTES = ChatFile(
    path="/f/assistant/t2/notes.txt", name="notes.txt", media_type="text/plain", size=3
)


def test_the_attached_file_line_is_worded_as_written() -> None:
    assert ATTACHED_FILE == (
        'The person attached "{name}" ({media_type}, {size} bytes), saved at {path}.'
    )


def test_a_message_with_files_is_its_text_then_a_line_per_file() -> None:
    events = [
        TurnStart(turn=0),
        UserMessageEvent(turn=0, message=UserMessage(content="read these"), files=(PAGE, NOTES)),
    ]

    (message,) = derive_messages(events)

    assert message == UserMessage(
        content="read these\n\n"
        'The person attached "page.png" (image/png, 8 bytes), saved at /f/assistant/t1/page.png.\n'
        'The person attached "notes.txt" (text/plain, 3 bytes), saved at /f/assistant/t2/notes.txt.'
    )


def test_a_message_without_files_derives_exactly_as_before() -> None:
    said = UserMessage(content="hello\n\n")
    events = [TurnStart(turn=0), UserMessageEvent(turn=0, message=said)]

    (message,) = derive_messages(events)

    assert message is said


def test_a_message_logged_before_files_existed_still_loads_with_none() -> None:
    old = '{"type":"user/message","turn":0,"message":{"role":"user","content":"hi"}}'

    event = UserMessageEvent.model_validate_json(old)

    assert event.files == ()
    assert derive_messages([event]) == [UserMessage(content="hi")]


def test_a_message_with_files_round_trips_as_json() -> None:
    event = UserMessageEvent(turn=0, message=UserMessage(content="x"), files=(PAGE,))

    assert UserMessageEvent.model_validate_json(event.model_dump_json()) == event
