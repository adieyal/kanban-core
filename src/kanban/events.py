from __future__ import annotations

from collections.abc import Iterator, Mapping
from copy import deepcopy
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Protocol

# ============= EVENTS SYSTEM =============


class EventRegistry:
    """Singleton-by-explicit-dependency; avoids module-global state."""

    def __init__(self, builtin: dict[str, str] | None = None):
        self._events: dict[str, str] = dict(builtin) if builtin is not None else {}

    def register(self, code: str, description: str) -> None:
        if code in self._events:
            raise ValueError(f"Event {code!r} already registered")
        self._events[code] = description

    def __contains__(self, code: str) -> bool:
        return code in self._events

    def __iter__(self) -> Iterator[str]:
        yield from self._events.keys()


builtin_events = {
    "board.created": "Board created",
    "board.updated": "Board updated",
    "board.deleted": "Board deleted",
    "board.tick": "Scheduled board automation evaluated",
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
    schema_version: int = 1
    correlation_id: str | None = None
    causation_id: str | None = None
    aggregate_version: int | None = None

    def __post_init__(self) -> None:
        # A frozen dataclass does not make nested dictionaries immutable. Detach the
        # payload from the caller so later mutations cannot rewrite event history.
        object.__setattr__(self, "data", deepcopy(self.data))

    def to_dict(self) -> dict[str, Any]:
        """Converts the event to a dictionary with serializable types."""

        def _serialize_value(v: Any) -> Any:
            if isinstance(v, set):
                return sorted((_serialize_value(item) for item in v), key=repr)
            if isinstance(v, list | tuple):
                return [_serialize_value(item) for item in v]
            if isinstance(v, Mapping):
                return {key: _serialize_value(value) for key, value in v.items()}
            if isinstance(v, datetime):
                return v.isoformat()
            if isinstance(v, timedelta):
                return v.total_seconds()
            if isinstance(v, Enum):
                return _serialize_value(v.value)
            if is_dataclass(v) and not isinstance(v, type):
                return {
                    item.name: _serialize_value(getattr(v, item.name))
                    for item in fields(v)
                }
            return v

        return {
            "id": self.id,
            "type": self.type,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "schema_version": self.schema_version,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "aggregate_version": self.aggregate_version,
            "data": _serialize_value(self.data),
        }


class EventPublisher(Protocol):
    """Outbound port used only after the aggregate commit succeeds."""

    def publish(self, event: Event) -> None: ...
