"""Automation evaluates immutable facts and returns requested business actions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

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


AutomationAction = MoveCardAction
AutomationRule = Callable[[Event, AutomationFacts], tuple[AutomationAction, ...]]


class AutomationRunner(Protocol):
    def evaluate(
        self, event: Event, facts: AutomationFacts
    ) -> tuple[AutomationAction, ...]: ...


class SyncAutomationRunner:
    def __init__(self, rules: tuple[AutomationRule, ...] = ()) -> None:
        self._rules = rules

    def evaluate(
        self, event: Event, facts: AutomationFacts
    ) -> tuple[AutomationAction, ...]:
        return tuple(action for rule in self._rules for action in rule(event, facts))
