from __future__ import annotations

import logging
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import datetime
from threading import RLock

from kanban.spi import Event

logger = logging.getLogger(__name__)


class EventBus:
    """Thread-safe in-memory event publisher with bounded event history."""

    def __init__(self, max_size: int = 1000) -> None:
        self._subscriptions: dict[str, list[Callable[[Event], None]]] = defaultdict(
            list
        )
        self._events: deque[Event] = deque(maxlen=max_size)
        self._lock = RLock()

    def subscribe(self, event_type: str, handler: Callable[[Event], None]) -> None:
        with self._lock:
            self._subscriptions[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable[[Event], None]) -> None:
        with self._lock:
            handlers = self._subscriptions.get(event_type, [])
            if handler in handlers:
                handlers.remove(handler)
            if not handlers:
                self._subscriptions.pop(event_type, None)

    def publish(self, event: Event) -> None:
        with self._lock:
            self._events.append(event)
            handlers = list(
                self._subscriptions.get(event.type, [])
                + self._subscriptions.get("*", [])
            )
        for handler in handlers:
            try:
                handler(Event(**event.__dict__))
            except Exception:
                logger.exception("Event handler failed for %s", event.type)

    def get_events(self, since: datetime | None = None) -> list[Event]:
        with self._lock:
            events = list(self._events)
        if since is not None:
            events = [event for event in events if event.timestamp >= since]
        return events
