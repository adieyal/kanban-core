"""Public automation contracts for move-based business reactions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
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

    def __post_init__(self) -> None:
        object.__setattr__(self, "attributes", freeze_attributes(self.attributes))


@dataclass(frozen=True, slots=True)
class AutomationColumnFacts:
    id: str
    name: str


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


AutomationAction: TypeAlias = MoveCardAction


class AutomationRunner(Protocol):
    def evaluate(
        self, event: Event, facts: AutomationFacts
    ) -> tuple[AutomationAction, ...]: ...
