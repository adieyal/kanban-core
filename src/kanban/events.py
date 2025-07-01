from __future__ import annotations

import logging
import threading
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

# ============= EVENTS SYSTEM =============


class EventRegistry:
    """Singleton-by-explicit-dependency; avoids module-global state."""

    def __init__(self, builtin: dict[str, str] | None = None):
        self._events: dict[str, str] = builtin or {}

    def register(self, code: str, description: str):
        if code in self._events:
            raise ValueError(f"Event {code!r} already registered")
        self._events[code] = description

    def __contains__(self, code: str) -> bool:
        return code in self._events

    def __iter__(self):
        yield from self._events.keys()


builtin_events = {
    "board.created": "Board created",
    "board.updated": "Board updated",
    "board.deleted": "Board deleted",
    "column.created": "Column created",
    "column.updated": "Column updated",
    "column.deleted": "Column deleted",
    "column.moved": "Column moved",
    "card.created": "Card created",
    "card.updated": "Card updated",
    "card.deleted": "Card deleted",
    "card.moved": "Card moved",
    "card.blocked": "Card blocked",
    "card.unblocked": "Card unblocked",
    "wip.limit.reached": "WIP limit reached",
    "workflow.transition": "Workflow transition",
    "automation.triggered": "Automation triggered",
    "automation.failed": "Automation failed",
}

CORE_EVENTS = EventRegistry(builtin_events)
CARD_MOVED = "card.moved"
CARD_UPDATED = "card.updated"
CARD_CREATED = "card.created"
CARD_DELETED = "card.deleted"
COLUMN_UPDATED = "column.updated"
COLUMN_CREATED = "column.created"
COLUMN_DELETED = "column.deleted"
BOARD_CREATED = "board.created"
BOARD_UPDATED = "board.updated"
BOARD_DELETED = "board.deleted"
CARD_BLOCKED = "card.blocked"
CARD_UNBLOCKED = "card.unblocked"


@dataclass(frozen=True)
class Event:
    """Immutable event object. Handlers receive a copy."""

    type: str
    entity_id: str
    entity_type: str
    id: str
    timestamp: datetime
    data: dict[str, Any] = field(default_factory=dict)
    user_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Converts the event to a dictionary with serializable types."""

        def _serialize_value(v):
            if isinstance(v, set):
                return sorted(list(v))  # sorted for deterministic output
            if isinstance(v, datetime):
                return v.isoformat()
            if isinstance(v, timedelta):
                return v.total_seconds()
            if isinstance(v, Enum):
                return v.value
            return v

        return {
            "id": self.id,
            "type": self.type,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "data": {k: _serialize_value(v) for k, v in self.data.items()},
        }


class EventBus:
    """
    Simple event bus for domain events.
    (REVISED: A-2, A-9) Now supports unsubscribing and has a max event retention size.
    """

    def __init__(self, max_size: int = 10000):
        self._subscriptions: dict[str, set[Callable[[Event], None]]] = defaultdict(set)
        self._lock = threading.RLock()  # re-entrant
        self._events: deque[Event] = deque(maxlen=max_size)

    def subscribe(self, event_code: str, handler: Callable[[Event], None]):
        with self._lock:
            self._subscriptions[event_code].add(handler)

    def unsubscribe(self, event_code: str, handler: Callable[[Event], None]):
        with self._lock:
            self._subscriptions.get(event_code, set()).discard(handler)

    def publish(self, event: Event):
        with self._lock:
            self._events.append(event)  # retain in history
            handlers = self._subscriptions.get(
                event.type, set()
            ) | self._subscriptions.get("*", set())
        for h in handlers.copy():  # shallow copy for safe iteration
            try:
                h(event)
            except Exception as exc:
                # Attach event info for easier debugging; leave policy decision to caller
                logging.exception(
                    "Event handler %s failed on %s", h, event.id, exc_info=exc
                )

    def get_events(self, since: datetime | None = None) -> list[Event]:
        with self._lock:
            events = list(self._events)
        if since:
            return [e for e in events if e.timestamp and e.timestamp > since]
        return events
