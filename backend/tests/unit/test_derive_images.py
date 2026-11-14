"""What the model is shown of a history's images: all of them, but a note for each one hidden."""

from __future__ import annotations

from harness.files import ChatFile
from harness.llm import (
    AssistantMessage,
    Image,
    Message,
    Text,
    ToolCall,
    ToolMessage,
    UserMessage,
    images_of,
)
from harness.prompts import IMAGE_HIDDEN, IMAGE_NOT_SHOWN
from harness.session.domain.images import ImagesHidden
from harness.session.domain.model_history import derive_messages, without_images
from harness.session.domain.models import (
    AssistantMessageEvent,
    SessionEvent,
    ToolCallEvent,
    ToolResultEvent,
    TurnStart,
    UserMessageEvent,
)
from harness.session.repository.jsonl_session_repository import JsonlSessionRepository
from harness.session.service.session_service import SessionService

FIRST = Image(media_type="image/png", sha256="1" * 64, size=3)
SECOND = Image(media_type="image/jpeg", sha256="2" * 64, size=3)
THIRD = Image(media_type="image/webp", sha256="3" * 64, size=3)
CALL = ToolCall(id="c1", name="srv__snap", arguments="{}")
MANY = 30


def person_then_tool(*, attached: tuple[Image, ...], returned: tuple[Image, ...]) -> list:
    """The person's message showing `attached`, then a tool call whose result shows `returned`."""
    return [
        TurnStart(turn=0),
        UserMessageEvent(turn=0, message=UserMessage(content="look", images=attached)),
        AssistantMessageEvent(
            turn=0, step=0, message=AssistantMessage(content="", tool_calls=(CALL,))
        ),
        ToolCallEvent(turn=0, step=0, call=CALL),
        ToolResultEvent(
            turn=0,
            step=0,
            message=ToolMessage(tool_call_id="c1", content=(Text(text="shot"), *returned)),
        ),
    ]


def shown(messages: list[Message]) -> list[Image]:
    return [image for message in messages for image in images_of(message)]


def test_the_image_notes_are_worded_as_written() -> None:
    assert IMAGE_NOT_SHOWN == "[an image that could not be shown]"
    assert IMAGE_HIDDEN == (
        "[This image was removed to reduce the request size and is no longer visible. "
        "Do not make claims about its contents from memory. If needed, retrieve it again "
        "with an available tool or ask the user to attach it again.]"
    )


def test_without_a_hide_every_image_is_shown_however_many_or_large() -> None:
    big = tuple(
        Image(media_type="image/png", sha256=f"{n:064x}", size=50_000_000) for n in range(MANY)
    )
    first, *rest = big
    events = person_then_tool(attached=(first,), returned=tuple(rest))

    assert shown(derive_messages(events)) == list(big)


def test_a_hide_notes_the_log_s_first_images_across_person_and_result() -> None:
    events = person_then_tool(attached=(FIRST,), returned=(SECOND, THIRD))

    person, _, result = derive_messages([*events, ImagesHidden(turn=0, through=2)])

    assert person == UserMessage(content=f"look\n{IMAGE_HIDDEN}")
    assert result.content == (Text(text="shot"), Text(text=IMAGE_HIDDEN), THIRD)


def test_a_hidden_image_in_a_result_becomes_the_note_in_its_place() -> None:
    events = person_then_tool(attached=(), returned=(FIRST, SECOND))

    _, _, result = derive_messages([*events, ImagesHidden(turn=0, through=1)])

    assert result.content == (Text(text="shot"), Text(text=IMAGE_HIDDEN), SECOND)


def test_the_person_s_hidden_images_are_dropped_with_a_line_each() -> None:
    events = person_then_tool(attached=(FIRST, SECOND, THIRD), returned=())

    person = derive_messages([*events, ImagesHidden(turn=0, through=2)])[0]

    assert person == UserMessage(content=f"look\n{IMAGE_HIDDEN}\n{IMAGE_HIDDEN}", images=(THIRD,))


def test_a_smaller_hide_after_a_larger_one_brings_nothing_back() -> None:
    events = person_then_tool(attached=(FIRST,), returned=(SECOND, THIRD))
    hides = [ImagesHidden(turn=0, through=2), ImagesHidden(turn=0, through=1)]

    assert shown(derive_messages([*events, *hides])) == [THIRD]


def test_the_same_log_derives_the_same_request() -> None:
    events = person_then_tool(attached=(FIRST,), returned=(SECOND, THIRD))

    assert derive_messages(events) == derive_messages(list(events))


def test_without_images_every_image_is_a_note() -> None:
    derived = derive_messages(person_then_tool(attached=(FIRST,), returned=(SECOND,)))

    person, _, result = without_images(derived)

    assert shown([person, result]) == []
    assert person.content == f"look\n{IMAGE_NOT_SHOWN}"
    assert result.content == (Text(text="shot"), Text(text=IMAGE_NOT_SHOWN))


def test_a_history_without_images_is_left_as_it_was() -> None:
    said = UserMessage(content="hello")
    events = [TurnStart(turn=0), UserMessageEvent(turn=0, message=said)]

    (message,) = derive_messages(events)

    assert message is said


def test_the_person_s_images_ride_beside_the_lines_for_their_files() -> None:
    page = ChatFile(path="/f/a/page.png", name="page.png", media_type="image/png", size=8)
    message = UserMessage(content="read", images=(FIRST,))
    events = [TurnStart(turn=0), UserMessageEvent(turn=0, message=message, files=(page,))]

    (derived,) = derive_messages(events)

    assert derived.images == (FIRST,)
    assert derived.content.startswith('read\n\nThe person attached "page.png"')


def test_a_log_written_before_images_existed_still_loads() -> None:
    person = '{"type":"user/message","turn":0,"message":{"role":"user","content":"hi"}}'
    result = (
        '{"type":"tool/result","turn":0,"step":0,'
        '"message":{"role":"tool","tool_call_id":"c1","content":[{"type":"text","text":"ok"}]}}'
    )

    loaded_person = UserMessageEvent.model_validate_json(person)
    loaded_result = ToolResultEvent.model_validate_json(result)

    assert loaded_person.message == UserMessage(content="hi", images=())
    assert loaded_result.message.content == (Text(text="ok"),)


async def test_an_image_survives_the_log_repair_and_derive(tmp_path) -> None:
    service = SessionService(JsonlSessionRepository(tmp_path), new_id=lambda: "s")
    session = await service.create()
    lost = ToolCall(id="c2", name="srv__snap", arguments="{}")
    events: list[SessionEvent] = [
        *person_then_tool(attached=(FIRST,), returned=(SECOND,)),
        AssistantMessageEvent(
            turn=0, step=1, message=AssistantMessage(content="", tool_calls=(lost,))
        ),
    ]
    for event in events:
        session.append(event)
    await service.flush(session)

    resumed = await service.resume("s")

    repaired = resumed.events()[len(events) :]
    assert [event.message.tool_call_id for event in repaired] == ["c2"]
    assert resumed.events()[: len(events)] == events
    assert shown(derive_messages(resumed.events())) == [FIRST, SECOND]
