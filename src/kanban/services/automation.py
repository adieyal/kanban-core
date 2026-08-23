"""Automation evaluates immutable facts and returns requested business actions."""

from __future__ import annotations

from collections.abc import Callable

from ..events import Event
from ..spi.automation import AutomationAction, AutomationFacts

AutomationRule = Callable[[Event, AutomationFacts], tuple[AutomationAction, ...]]


class SyncAutomationRunner:
    def __init__(self, rules: tuple[AutomationRule, ...] = ()) -> None:
        self._rules = rules

    def evaluate(
        self, event: Event, facts: AutomationFacts
    ) -> tuple[AutomationAction, ...]:
        return tuple(action for rule in self._rules for action in rule(event, facts))
