"""A logged hide of the oldest images: what it covers, how far the next one reaches, and retries."""

from __future__ import annotations

from harness.llm import (
    IMAGES_OVER_LIMIT,
    ApplicationMessage,
    AssistantMessage,
    Completion,
    Image,
    LLMClient,
    Message,
    StreamFailure,
    Text,
    ToolCall,
    ToolMessage,
    UserMessage,
    images_of,
)
from harness.runtime.events import AgentCompleted, AgentFailed
from harness.runtime.service import Runtime
from harness.session.domain.compaction import CompactionEnd
from harness.session.domain.images import ImagesHidden, hidden_image_count
from harness.session.domain.log import Session
from harness.session.domain.model_history import derive_messages, hide_through_for_fewer_images
from harness.session.domain.models import (
    AssistantMessageEvent,
    SessionEvent,
    ToolCallEvent,
    ToolResultEvent,
    TurnStart,
    UserMessageEvent,
)
from tests.unit.fakes import OneModel
from tests.unit.helpers import new_session, no_images

FIRST, SECOND, THIRD = (
    Image(media_type="image/png", sha256=f"{n:064x}", size=3) for n in range(1, 4)
)
CALL = ToolCall(id="c1", name="srv__snap", arguments="{}")
SUMMARY = CompactionEnd(turn=None, message=ApplicationMessage(content="SUMMARY"))


def person(turn: int, *images: Image, bot_id: str = "b") -> list[SessionEvent]:
    """A turn opened by `bot_id` on the person's message showing `images`."""
    message = UserMessage(content="look", images=images)
    return [TurnStart(turn=turn, bot_id=bot_id), UserMessageEvent(turn=turn, message=message)]


def snapped(turn: int, image: Image) -> list[SessionEvent]:
    """The bot of `turn` calls a tool whose result shows `image`."""
    call = AssistantMessage(content="", tool_calls=(CALL,))
    result = ToolMessage(tool_call_id="c1", content=(Text(text="shot"), image))
    return [
        AssistantMessageEvent(turn=turn, step=0, message=call),
        ToolCallEvent(turn=turn, step=0, call=CALL),
        ToolResultEvent(turn=turn, step=0, message=result),
    ]


def shown(events: list[SessionEvent]) -> list[Image]:
    return [image for message in derive_messages(events) for image in images_of(message)]


def test_the_largest_hide_logged_wins() -> None:
    hides = [ImagesHidden(turn=0, through=3), ImagesHidden(turn=1, through=1)]

    assert hidden_image_count([]) == 0
    assert hidden_image_count(hides) == 3


def test_the_next_hide_covers_the_count_asked_for_past_the_last() -> None:
    events = [*person(0, FIRST, SECOND, THIRD), ImagesHidden(turn=0, through=1)]

    assert hide_through_for_fewer_images(events, 1) == 2
    assert hide_through_for_fewer_images(events, 5) == 3


def test_with_every_image_hidden_there_is_no_next_hide() -> None:
    events = [*person(0, FIRST), ImagesHidden(turn=0, through=1)]

    assert hide_through_for_fewer_images(events, 1) is None


def test_a_hide_reaches_past_the_compaction_boundary() -> None:
    events = [*person(0, FIRST), SUMMARY, *person(1, SECOND, THIRD)]

    through = hide_through_for_fewer_images(events, 1)

    assert through == 2
    assert shown([*events, ImagesHidden(turn=1, through=through)]) == [THIRD]


def test_another_bot_s_images_count_but_the_hide_reaches_the_listener_s() -> None:
    events = [*person(0, bot_id="a"), *snapped(0, FIRST), *person(1, SECOND, bot_id="b")]

    assert shown(events) == [SECOND]
    assert hide_through_for_fewer_images(events, 1) == 2


class OverTheLimit(LLMClient):
    """Refuses every request with too many images, until `refusals` run out, asking for one."""

    def __init__(self, refusals: int) -> None:
        self.refusals = refusals
        self.seen: list[list[Message]] = []

    async def stream_completion(self, messages, model, *, tools=None):
        self.seen.append(list(messages))
        if len(self.seen) <= self.refusals:
            yield StreamFailure(reason="too many", code=IMAGES_OVER_LIMIT, images_to_hide=1)
            return
        yield Completion(full_text="seen")


async def run(client: LLMClient, session: Session) -> list:
    runtime = Runtime(models=OneModel(client, vision=True), images=no_images())
    return [event async for event in runtime.run("next", session=session, bot_id="b")]


def seeded(*images: Image) -> Session:
    session = new_session()
    for event in person(0, *images):
        session.append(event)
    return session


async def test_a_refusal_logs_a_hide_and_retries_the_step() -> None:
    client = OverTheLimit(refusals=1)
    session = seeded(FIRST, SECOND)

    events = await run(client, session)

    assert events[-1] == AgentCompleted(text="seen")
    assert [e for e in session.events() if isinstance(e, ImagesHidden)] == [
        ImagesHidden(turn=1, through=1)
    ]
    assert [image for m in client.seen[-1] for image in images_of(m)] == [SECOND]


async def test_with_nothing_left_to_hide_the_refusal_fails_the_turn() -> None:
    session = seeded(FIRST)

    events = await run(OverTheLimit(refusals=5), session)

    assert events[-1] == AgentFailed(reason="too many")
    assert hidden_image_count(session.events()) == 1
