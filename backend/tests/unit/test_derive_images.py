"""What the model is shown of a history's images: the newest ten, and a note for each older one."""

from __future__ import annotations

from harness.files import ChatFile
from harness.llm.messages import (
    AssistantMessage,
    Image,
    Message,
    Text,
    ToolCall,
    ToolMessage,
    UserMessage,
    images_of,
)
from harness.prompts import IMAGE_NOT_SHOWN
from harness.session.derive import (
    IMAGE_BYTES_KEPT,
    IMAGES_KEPT,
    derive_messages,
    without_images,
)
from harness.session.models import (
    AssistantMessageEvent,
    SessionEvent,
    ToolCallEvent,
    ToolResultEvent,
    TurnStart,
    UserMessageEvent,
)
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService

FIRST = Image(media_type="image/png", sha256="1" * 64, size=3)
SECOND = Image(media_type="image/jpeg", sha256="2" * 64, size=3)
THIRD = Image(media_type="image/webp", sha256="3" * 64, size=3)
CALL = ToolCall(id="c1", name="srv__snap", arguments="{}")
PAST_THE_LIMIT = tuple(
    Image(media_type="image/png", sha256=f"{n:064x}", size=3) for n in range(IMAGES_KEPT + 1)
)


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


def test_the_image_note_is_worded_as_written() -> None:
    assert IMAGE_NOT_SHOWN == (
        "[an earlier image, no longer shown: only the newest images are kept]"
    )
    assert IMAGES_KEPT == 10
    assert IMAGE_BYTES_KEPT == 12_000_000


def test_images_past_the_byte_budget_become_the_note_even_under_the_count() -> None:
    big = [
        Image(media_type="image/png", sha256=f"{n:064x}", size=IMAGE_BYTES_KEPT // 2 + 1)
        for n in range(3)
    ]
    events = person_then_tool(attached=(big[0],), returned=(big[1], big[2]))

    person, _, result = derive_messages(events)

    assert shown([person, result]) == [big[2]]
    assert person == UserMessage(content=f"look\n{IMAGE_NOT_SHOWN}")
    assert result.content == (Text(text="shot"), Text(text=IMAGE_NOT_SHOWN), big[2])


def test_of_one_image_past_the_limit_only_the_newest_reach_the_model() -> None:
    oldest, *newest = PAST_THE_LIMIT
    events = person_then_tool(attached=(oldest,), returned=tuple(newest))

    person, _, result = derive_messages(events)

    assert shown([person, result]) == newest
    assert person == UserMessage(content=f"look\n{IMAGE_NOT_SHOWN}")
    assert result.content == (Text(text="shot"), *newest)


def test_an_older_image_in_a_result_becomes_the_note_in_its_place() -> None:
    oldest, *newest = PAST_THE_LIMIT
    events = person_then_tool(attached=(), returned=PAST_THE_LIMIT)

    _, _, result = derive_messages(events)

    assert result.content == (Text(text="shot"), Text(text=IMAGE_NOT_SHOWN), *newest)


def test_the_person_s_older_images_are_dropped_with_a_line_each() -> None:
    oldest, *newest = PAST_THE_LIMIT
    events = person_then_tool(attached=PAST_THE_LIMIT, returned=())

    person = derive_messages(events)[0]

    assert person == UserMessage(content=f"look\n{IMAGE_NOT_SHOWN}", images=tuple(newest))


def test_up_to_the_limit_every_image_is_shown() -> None:
    first, *rest = PAST_THE_LIMIT[:IMAGES_KEPT]
    events = person_then_tool(attached=(first,), returned=tuple(rest))

    assert shown(derive_messages(events)) == [first, *rest]


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
