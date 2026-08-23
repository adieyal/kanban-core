"""Commit boundary for persistence records and resulting events."""

from __future__ import annotations

from typing import Protocol

from .events import Event
from .repositories import BoardSnapshot


class KanbanUnitOfWork(Protocol):
    """Atomic persistence port; mutable domain objects never cross this boundary."""

    def save(
        self,
        board: BoardSnapshot,
        events: tuple[Event, ...],
        expected_version: int | None = None,
    ) -> BoardSnapshot: ...

    def delete(
        self,
        board_id: str,
        events: tuple[Event, ...],
        expected_version: int,
    ) -> None: ...

    def emit(self, events: tuple[Event, ...], aggregate_version: int) -> None: ...
