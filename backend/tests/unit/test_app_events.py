"""`AppEventService` puts what is published on every open subscriber's queue."""

import asyncio
from collections.abc import AsyncIterator

from harness.app_events import AppEvent, AppEventService, BotsChangedAppEvent, TurnStartedAppEvent

TIMEOUT = 1.0


def read(subscriber: AsyncIterator[AppEvent]) -> asyncio.Task[AppEvent]:
    """The subscriber's next event, failing rather than waiting forever."""
    return asyncio.create_task(asyncio.wait_for(anext(subscriber), timeout=TIMEOUT))


async def test_every_subscriber_receives_a_published_event():
    events = AppEventService()
    first, second = events.subscribe(), events.subscribe()
    reads = (read(first), read(second))
    await asyncio.sleep(0)
    events.publish(TurnStartedAppEvent(chat_id="c1"))
    assert await asyncio.gather(*reads) == [TurnStartedAppEvent(chat_id="c1")] * 2
    await first.aclose()
    await second.aclose()


async def test_a_subscriber_that_stops_reading_is_removed():
    events = AppEventService()
    leaving, staying = events.subscribe(), events.subscribe()
    reads = (read(leaving), read(staying))
    await asyncio.sleep(0)
    events.publish(TurnStartedAppEvent(chat_id="c1"))
    await asyncio.gather(*reads)
    await leaving.aclose()
    events.publish(BotsChangedAppEvent())
    assert await read(staying) == BotsChangedAppEvent()
    assert len(events._queues) == 1
    await staying.aclose()
