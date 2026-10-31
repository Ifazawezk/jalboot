import asyncio
import threading

from jalboot.api import events
from jalboot.api.events import Broker, sse_frame, stream_events


def test_a_frame_names_the_event_and_keeps_the_data_on_one_line():
    frame = sse_frame({"type": "text.delta", "delta": "نص\nآخر"}, 7)
    assert frame == 'id: 7\nevent: text.delta\ndata: {"delta":"نص\\nآخر"}\n\n'


def test_a_frame_without_an_id_is_allowed():
    assert sse_frame({"type": "x"}).startswith("event: x\n")


def test_a_published_event_reaches_a_subscriber_from_another_thread():
    async def scenario():
        broker = Broker()
        subscription = broker.subscribe("t")
        thread = threading.Thread(target=broker.publish, args=("t", {"type": "a"}))
        thread.start()
        thread.join()
        return await asyncio.wait_for(subscription.queue.get(), 1)

    assert asyncio.run(scenario()) == (1, {"type": "a"})


def test_reconnecting_with_last_event_id_replays_only_what_was_missed():
    async def scenario():
        broker = Broker()
        for name in ("a", "b", "c"):
            broker.publish("t", {"type": name})
        subscription = broker.subscribe("t", after=1)
        first = await asyncio.wait_for(subscription.queue.get(), 1)
        second = await asyncio.wait_for(subscription.queue.get(), 1)
        return first, second, subscription.queue.empty()

    first, second, empty = asyncio.run(scenario())
    assert first == (2, {"type": "b"})
    assert second == (3, {"type": "c"})
    assert empty


def test_a_new_subscriber_with_no_id_gets_only_new_events():
    async def scenario():
        broker = Broker()
        broker.publish("t", {"type": "old"})
        subscription = broker.subscribe("t")
        return subscription.queue.empty()

    assert asyncio.run(scenario())


def test_topics_are_separate():
    async def scenario():
        broker = Broker()
        subscription = broker.subscribe("mine")
        broker.publish("yours", {"type": "secret"})
        await asyncio.sleep(0)
        return subscription.queue.empty()

    assert asyncio.run(scenario())


def test_leaving_the_stream_unsubscribes():
    async def scenario():
        broker = Broker()
        subscription = broker.subscribe("t")
        stream = stream_events(subscription)
        await stream.__anext__()
        await stream.aclose()
        return broker.count("t")

    assert asyncio.run(scenario()) == 0


def test_a_slow_subscriber_is_dropped_not_grown_forever(monkeypatch):
    monkeypatch.setattr(events, "QUEUE_LIMIT", 2)

    async def scenario():
        broker = Broker()
        subscription = broker.subscribe("t")
        for number in range(5):
            broker.publish("t", {"type": str(number)})
        await asyncio.sleep(0.01)
        return broker.count("t"), subscription.queue.get_nowait() is events.CLOSED

    count, closed = asyncio.run(scenario())
    assert count == 0
    assert closed
