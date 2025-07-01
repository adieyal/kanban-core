from __future__ import annotations

import copy
import threading
from abc import ABC, abstractmethod

from .exceptions import ConcurrencyError
from .models import Board

# ============= REPOSITORY PATTERN =============


class IKanbanRepository(ABC):
    @abstractmethod
    def get(self, board_id: str) -> Board | None:
        pass

    # FIX 3.2.1: The save method now returns the persisted board object.
    @abstractmethod
    def save(self, board: Board, expected_version: int | None = None) -> Board:
        pass

    @abstractmethod
    def delete(self, board_id: str) -> None:
        pass

    @abstractmethod
    def list_all(self) -> list[Board]:
        pass

    @abstractmethod
    def exists(self, board_id: str) -> bool:
        pass


def snapshot_board(board: Board) -> Board:
    """
    Create a deep copy of the board for safe usage.
    """
    if board is None:
        return None
    return copy.deepcopy(board)


class InMemoryKanbanRepository(IKanbanRepository):
    """
    (REVISED: A-3, A-7) An in-memory repository that is now thread-safe and uses deepcopy.
    Now supports optimistic concurrency control.
    """

    def __init__(self):
        self._boards: dict[str, Board] = {}
        self._lock = threading.Lock()

    def get(self, board_id: str) -> Board | None:
        with self._lock:
            board = self._boards.get(board_id)
            return snapshot_board(board) if board else None

    def save(self, board: Board, expected_version: int | None = None) -> Board:
        with self._lock:
            current = self._boards.get(board.id)
            if (
                current
                and expected_version is not None
                and current.version != expected_version
            ):
                raise ConcurrencyError(
                    f"Expected v{expected_version}, found v{current.version}"
                )

            board.version = (
                current.version if current else 0
            ) + 1  # mutate caller copy
            self._boards[board.id] = snapshot_board(board)
            return snapshot_board(board)

    def delete(self, board_id: str) -> None:
        with self._lock:
            if board_id in self._boards:
                del self._boards[board_id]

    def list_all(self) -> list[Board]:
        with self._lock:
            return [snapshot_board(b) for b in self._boards.values()]

    def exists(self, board_id: str) -> bool:
        with self._lock:
            return board_id in self._boards
