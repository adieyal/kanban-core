from __future__ import annotations

from dataclasses import replace

from kanban.spi import (
    BoardSnapshot,
    Event,
    EventPublisher,
    KanbanRepository,
    KanbanUnitOfWork,
)


class SynchronousKanbanUnitOfWork(KanbanUnitOfWork):
    """Reference unit of work that saves state before publishing events."""

    def __init__(
        self, repository: KanbanRepository, event_publisher: EventPublisher
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def save(
        self,
        board: BoardSnapshot,
        events: tuple[Event, ...],
        expected_version: int | None = None,
    ) -> BoardSnapshot:
        saved = self._repository.save(board, expected_version=expected_version)
        for event in events:
            self._event_publisher.publish(
                replace(event, aggregate_version=saved.version)
            )
        return saved

    def delete(
        self,
        board_id: str,
        events: tuple[Event, ...],
        expected_version: int,
    ) -> None:
        self._repository.delete(board_id, expected_version=expected_version)
        for event in events:
            self._event_publisher.publish(
                replace(event, aggregate_version=expected_version)
            )

    def emit(self, events: tuple[Event, ...], aggregate_version: int) -> None:
        for event in events:
            self._event_publisher.publish(
                replace(event, aggregate_version=aggregate_version)
            )
