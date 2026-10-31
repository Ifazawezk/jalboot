"""In-process publish and subscribe for live updates.

Chat turns run on worker threads and server-sent event streams run on the event
loop, so publishing hands each event to the subscriber's loop safely. Each topic keeps
its recent events, so a client that reconnects with Last-Event-ID misses nothing. A
subscriber that stops reading is dropped rather than allowed to grow without limit.

This works for one server process. Running several would need a shared broker such
as PostgreSQL LISTEN/NOTIFY or Redis; see the limits in the README.
"""

from __future__ import annotations

import asyncio
import json
import threading
from collections import deque
from typing import Any, AsyncIterator

QUEUE_LIMIT = 256
HISTORY_LIMIT = 200
KEEPALIVE_SECONDS = 15.0
CLOSED = object()


class Subscription:
    def __init__(self, broker: "Broker", topic: str, loop: asyncio.AbstractEventLoop):
        self.broker = broker
        self.topic = topic
        self.loop = loop
        self.queue: asyncio.Queue[Any] = asyncio.Queue(QUEUE_LIMIT)

    def _put(self, item: Any) -> None:
        try:
            self.queue.put_nowait(item)
        except asyncio.QueueFull:
            self.broker.unsubscribe(self)
            while not self.queue.empty():
                self.queue.get_nowait()
            self.queue.put_nowait(CLOSED)

    def deliver(self, item: Any) -> None:
        self.loop.call_soon_threadsafe(self._put, item)

    def close(self) -> None:
        self.broker.unsubscribe(self)


class Broker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._topics: dict[str, set[Subscription]] = {}
        self._history: dict[str, deque[tuple[int, dict[str, Any]]]] = {}
        self._counters: dict[str, int] = {}

    def subscribe(self, topic: str, after: int | None = None) -> Subscription:
        """Registers first and replays second, under the lock, so an event published in
        between is neither lost nor sent twice."""
        subscription = Subscription(self, topic, asyncio.get_running_loop())
        with self._lock:
            self._topics.setdefault(topic, set()).add(subscription)
            if after is not None:
                for event_id, event in self._history.get(topic, ()):
                    if event_id > after:
                        subscription.deliver((event_id, event))
        return subscription

    def unsubscribe(self, subscription: Subscription) -> None:
        with self._lock:
            members = self._topics.get(subscription.topic)
            if members is not None:
                members.discard(subscription)
                if not members:
                    del self._topics[subscription.topic]

    def publish(self, topic: str, event: dict[str, Any]) -> int:
        with self._lock:
            self._counters[topic] = self._counters.get(topic, 0) + 1
            event_id = self._counters[topic]
            self._history.setdefault(topic, deque(maxlen=HISTORY_LIMIT)).append((event_id, event))
            members = list(self._topics.get(topic, ()))
        for member in members:
            try:
                member.deliver((event_id, event))
            except RuntimeError:
                # The subscriber's loop has closed, so its stream is already gone.
                self.unsubscribe(member)
        return event_id

    def count(self, topic: str) -> int:
        with self._lock:
            return len(self._topics.get(topic, ()))


def sse_frame(event: dict[str, Any], event_id: int | None = None) -> str:
    """The event name goes on the event line, and the data line holds the rest."""
    name = event.get("type", "message")
    data = {key: value for key, value in event.items() if key != "type"}
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str)
    head = f"id: {event_id}\n" if event_id is not None else ""
    return f"{head}event: {name}\ndata: {body}\n\n"


async def stream_events(subscription: Subscription) -> AsyncIterator[str]:
    """Yields SSE text until the client leaves. Comment lines keep proxies from
    closing an idle connection."""
    try:
        yield ": connected\n\n"
        while True:
            try:
                item = await asyncio.wait_for(subscription.queue.get(), KEEPALIVE_SECONDS)
            except asyncio.TimeoutError:
                yield ": ping\n\n"
                continue
            if item is CLOSED:
                return
            event_id, event = item
            yield sse_frame(event, event_id)
    finally:
        subscription.close()


SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}
