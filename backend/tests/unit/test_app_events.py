"""`AppEvents` puts what is published on every open subscriber's queue."""

import asyncio

from harness.app_events import AppEvents, BotsChanged, TurnStarted


async def test_every_subscriber_receives_a_published_event():
    events = AppEvents()
    first, second = events.subscribe(), events.subscribe()
    reads = (asyncio.create_task(anext(first)), asyncio.create_task(anext(second)))
    await asyncio.sleep(0)
    events.publish(TurnStarted(chat_id="c1"))
    assert await asyncio.gather(*reads) == [TurnStarted(chat_id="c1")] * 2
    await first.aclose()
    await second.aclose()


async def test_a_subscriber_that_stops_reading_is_removed():
    events = AppEvents()
    leaving, staying = events.subscribe(), events.subscribe()
    reads = (asyncio.create_task(anext(leaving)), asyncio.create_task(anext(staying)))
    await asyncio.sleep(0)
    events.publish(TurnStarted(chat_id="c1"))
    await asyncio.gather(*reads)
    await leaving.aclose()
    events.publish(BotsChanged())
    assert await anext(staying) == BotsChanged()
    assert len(events._queues) == 1
    await staying.aclose()
