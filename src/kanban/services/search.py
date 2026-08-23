"""Search contracts operate on immutable detached card facts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class SearchCard:
    id: str
    title: str
    description: str
    assignee_ids: frozenset[str]
    is_blocked: bool


@dataclass(frozen=True, slots=True)
class SearchContext:
    cards: tuple[SearchCard, ...]


class CardSearcher(Protocol):
    def search(self, context: SearchContext, **filters: Any) -> tuple[str, ...]: ...


class InMemoryCardSearcher:
    def search(self, context: SearchContext, **filters: Any) -> tuple[str, ...]:
        results = list(context.cards)
        if text := filters.get("text"):
            text_lower = str(text).lower()
            results = [
                card
                for card in results
                if text_lower in card.title.lower()
                or text_lower in card.description.lower()
            ]
        if assignee_ids := filters.get("assignee_ids"):
            required = (
                {assignee_ids}
                if isinstance(assignee_ids, str)
                else set(assignee_ids)
            )
            results = [
                card for card in results if required.intersection(card.assignee_ids)
            ]
        if (is_blocked := filters.get("is_blocked")) is not None:
            results = [card for card in results if card.is_blocked == is_blocked]
        return tuple(card.id for card in results)
