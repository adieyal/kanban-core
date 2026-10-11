"""Public automation contracts for move-based business reactions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol, TypeAlias

from ..attributes import freeze_attributes
from ..events import Event


@dataclass(frozen=True, slots=True)
class AutomationCardFacts:
    id: str
    column_id: str
    title: str
    due_date: datetime | None
    archived: bool
    attributes: Mapping[str, object] = field(default_factory=dict)
    created_at: datetime | None = None
    entered_column_at: datetime | None = None

    blocked_reason: str | None = None
    blocked_at: datetime | None = None
    is_blocked: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "attributes", freeze_attributes(self.attributes))


@dataclass(frozen=True, slots=True)
class AutomationColumnFacts:
    id: str
    name: str
    max_age: timedelta | None = None


@dataclass(frozen=True, slots=True)
class AutomationFacts:
    cards: tuple[AutomationCardFacts, ...]
    columns: tuple[AutomationColumnFacts, ...]
    now: datetime

    def card(self, card_id: str) -> AutomationCardFacts | None:
        return next((card for card in self.cards if card.id == card_id), None)


@dataclass(frozen=True, slots=True)
class MoveCardAction:
    card_id: str
    to_column_id: str


@dataclass(frozen=True, slots=True)
class BlockCardAction:
    card_id: str
    reason: str


AutomationAction: TypeAlias = MoveCardAction | BlockCardAction


class AutomationRunner(Protocol):
    def evaluate(
        self, event: Event, facts: AutomationFacts
    ) -> tuple[AutomationAction, ...]: ...
