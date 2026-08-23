from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol

from .exceptions import InvalidPersistenceStateError
from .models import Board, Card, Column, ColumnPolicy


class FrozenMap(tuple[tuple[str, object], ...]):
    """Recursively immutable mapping used only inside persistence records."""


def _freeze(value: object) -> object:
    if isinstance(value, dict):
        return FrozenMap(
            tuple(sorted((str(key), _freeze(item)) for key, item in value.items()))
        )
    if isinstance(value, list | tuple):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set | frozenset):
        return frozenset(_freeze(item) for item in value)
    return value


def _thaw(value: object) -> object:
    if isinstance(value, FrozenMap):
        return {key: _thaw(item) for key, item in value}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, frozenset):
        return {_thaw(item) for item in value}
    return value


@dataclass(frozen=True, slots=True)
class BoardSnapshot:
    """Opaque immutable persistence record; contains no domain objects."""

    id: str
    version: int
    state: FrozenMap


def snapshot_board(board: Board) -> BoardSnapshot:
    state = asdict(board)
    state.pop("id")
    state.pop("version")
    frozen_state = _freeze(state)
    if not isinstance(frozen_state, FrozenMap):
        raise TypeError("Board state must freeze to a mapping")
    return BoardSnapshot(board.id, board.version, frozen_state)


def restore_board(snapshot: BoardSnapshot) -> Board:
    data = _thaw(snapshot.state)
    if not isinstance(data, dict):
        raise InvalidPersistenceStateError("Invalid board snapshot payload")

    columns = data.pop("columns")
    cards = data.pop("cards")

    owner_id = data.get("owner_id")
    if not isinstance(owner_id, str) or not owner_id.strip():
        raise InvalidPersistenceStateError("Board owner must be non-empty")

    board = Board(id=snapshot.id, version=snapshot.version, **data)
    board.columns = {
        key: Column(
            **{
                **value,
                "policy": ColumnPolicy(**value["policy"]),
            }
        )
        for key, value in columns.items()
    }
    board.cards = {key: Card(**value) for key, value in cards.items()}

    memberships: set[str] = set()
    for column in board.columns.values():
        if column.board_id != board.id:
            raise InvalidPersistenceStateError("Column belongs to another board")
        for card_id in column.card_ids:
            if card_id not in board.cards:
                raise InvalidPersistenceStateError("Column references an unknown card")
            if card_id in memberships:
                raise InvalidPersistenceStateError(
                    "Card belongs to more than one column"
                )
            memberships.add(card_id)
    if memberships != set(board.cards):
        raise InvalidPersistenceStateError(
            "Every card must belong to exactly one column"
        )

    positions = [column.position for column in board.columns.values()]
    if len(positions) != len(set(positions)):
        raise InvalidPersistenceStateError("Column positions must be unique")

    return board


class KanbanRepository(Protocol):
    """Persistence port. Infrastructure stores records, never mutable domain objects."""

    def get(self, board_id: str) -> BoardSnapshot | None: ...

    def save(
        self, board: BoardSnapshot, expected_version: int | None = None
    ) -> BoardSnapshot: ...

    def delete(self, board_id: str, expected_version: int) -> None: ...

    def list_all(self) -> list[BoardSnapshot]: ...

    def exists(self, board_id: str) -> bool: ...
