"""Search interfaces and implementations for the kanban library."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Board, Card


class ICardSearcher(ABC):
    """Interface for pluggable search strategies."""

    @abstractmethod
    def search(self, board: Board, **filters) -> list[Card]:
        """Search for cards within a board based on filter criteria."""
        pass


class InMemoryCardSearcher(ICardSearcher):
    """Default, in-memory search implementation."""

    def search(self, board: Board, **filters) -> list[Card]:
        results = list(board.cards.values())
        if text := filters.get("text"):
            text_lower = text.lower()
            results = [
                c
                for c in results
                if text_lower in c.title.lower() or text_lower in c.description.lower()
            ]
        if labels := filters.get("labels"):
            required_labels = set(labels)
            results = [
                c
                for c in results
                if required_labels.issubset(c.custom_fields.get("labels", set()))
            ]
        if assignee_ids := filters.get("assignee_ids"):
            results = [c for c in results if assignee_ids.intersection(c.assignee_ids)]
        if (is_blocked := filters.get("is_blocked")) is not None:
            results = [c for c in results if c.is_blocked() == is_blocked]
        return results