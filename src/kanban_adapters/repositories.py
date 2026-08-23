from __future__ import annotations

from dataclasses import replace
from threading import RLock

from kanban.spi import BoardSnapshot, ConcurrencyError, KanbanRepository


class InMemoryKanbanRepository(KanbanRepository):
    """Thread-safe reference repository with optimistic version checks."""

    def __init__(self) -> None:
        self._boards: dict[str, BoardSnapshot] = {}
        self._lock = RLock()

    def get(self, board_id: str) -> BoardSnapshot | None:
        with self._lock:
            return self._boards.get(board_id)

    def save(
        self, board: BoardSnapshot, expected_version: int | None = None
    ) -> BoardSnapshot:
        with self._lock:
            current = self._boards.get(board.id)
            current_version = current.version if current is not None else 0
            if expected_version is not None and current_version != expected_version:
                raise ConcurrencyError(
                    f"Expected v{expected_version}, found v{current_version}"
                )
            stored = replace(board, version=current_version + 1)
            self._boards[board.id] = stored
            return stored

    def delete(self, board_id: str, expected_version: int) -> None:
        with self._lock:
            current = self._boards.get(board_id)
            current_version = current.version if current is not None else 0
            if current_version != expected_version:
                raise ConcurrencyError(
                    f"Expected v{expected_version}, found v{current_version}"
                )
            self._boards.pop(board_id, None)

    def list_all(self) -> list[BoardSnapshot]:
        with self._lock:
            return list(self._boards.values())

    def exists(self, board_id: str) -> bool:
        with self._lock:
            return board_id in self._boards
