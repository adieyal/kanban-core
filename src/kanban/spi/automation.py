"""Public automation contracts for move-based business reactions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, TypeAlias

from ..events import Event


@dataclass(frozen=True, slots=True)
class AutomationCardFacts:
    id: str
    column_id: str
    title: str
    due_date: datetime | None
    archived: bool


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
