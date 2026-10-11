"""Import historical board state without replaying lifecycle commands."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from ..attributes import copy_attributes
from ..exceptions import (
    InvalidPersistenceStateError,
    PermissionError,
    ValidationError,
    require_aware_datetime,
)
from ..imports import BoardImport, CardImport, ColumnImport
from ..models import Board, Card, Column, ColumnPolicy
from ..permissions import Permission
from ..repositories import restore_board, snapshot_board
from .core import _KanbanServiceCore


def _nonempty(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{label} must be a nonempty string")


def _timestamp(value: datetime | None) -> None:
    if value is not None:
        require_aware_datetime(value)


def _build_board(data: BoardImport) -> Board:
    _nonempty(data.id, "Board ID")
    _nonempty(data.name, "Board name")
    _nonempty(data.owner_id, "Board owner")
    _timestamp(data.created_at)
    _timestamp(data.updated_at)
    for member in data.team_ids:
        _nonempty(member, "Team member ID")
    board = Board(
        id=data.id,
        name=data.name,
        description=data.description,
        owner_id=data.owner_id,
        team_ids=set(data.team_ids),
        created_at=data.created_at,
        updated_at=data.updated_at,
    )
    for position, column in enumerate(data.columns):
        if not isinstance(column, ColumnImport):
            raise ValidationError("Import columns must be ColumnImport values")
        _nonempty(column.id, "Column ID")
        _nonempty(column.name, "Column name")
        if column.id in board.columns:
            raise ValidationError("Import column IDs must be unique")
        if column.wip_limit is not None and (
            type(column.wip_limit) is not int or column.wip_limit < 0
        ):
            raise ValidationError("Column WIP limit must be a nonnegative integer")
        board.columns[column.id] = Column(
            id=column.id,
            board_id=board.id,
            name=column.name,
            position=position,
            policy=ColumnPolicy(column.wip_limit, column.max_age),
            color=column.color,
        )
    if len({column.name for column in board.columns.values()}) != len(board.columns):
        raise ValidationError("Import column names must be unique")
    for item in data.cards:
        if not isinstance(item, CardImport):
            raise ValidationError("Import cards must be CardImport values")
        _nonempty(item.id, "Card ID")
        _nonempty(item.title, "Card title")
        _nonempty(item.column_id, "Card column ID")
        if item.id in board.cards:
            raise ValidationError("Import card IDs must be unique")
        if item.column_id not in board.columns:
            raise ValidationError("Imported card references an unknown column")
        for identifier in item.assignee_ids | item.blocked_by:
            _nonempty(identifier, "Card reference ID")
        _timestamp(item.due_date)
        board.cards[item.id] = Card(
            id=item.id,
            title=item.title,
            description=item.description,
            attributes=copy_attributes(item.attributes),
            blocked_by=set(item.blocked_by),
            assignee_ids=set(item.assignee_ids),
            due_date=item.due_date,
            size=item.size,
            archived=item.archived,
            created_at=item.created_at,
            entered_column_at=item.entered_column_at,
            blocked_reason=item.blocked_reason,
            blocked_at=item.blocked_at,
        )
        board.columns[item.column_id].card_ids.append(item.id)
    # One representation is supplied. Reverse links are derived, never independently imported.
    for card in board.cards.values():
        for blocker_id in card.blocked_by:
            if blocker_id not in board.cards:
                raise ValidationError("Imported dependency references an unknown card")
            board.cards[blocker_id].blocks.add(card.id)
    remaining = {card.id: len(card.blocked_by) for card in board.cards.values()}
    ready = [card_id for card_id, count in remaining.items() if count == 0]
    visited = 0
    while ready:
        card_id = ready.pop()
        visited += 1
        for blocked_id in board.cards[card_id].blocks:
            remaining[blocked_id] -= 1
            if remaining[blocked_id] == 0:
                ready.append(blocked_id)
    if visited != len(board.cards):
        raise ValidationError("Imported card dependencies contain a cycle")
    board.configure_wip_groups(data.wip_groups)
    return board


class BoardImportService:
    def __init__(self, core: _KanbanServiceCore) -> None:
        self.core = core

    def import_board(self, user_id: str, data: BoardImport) -> Board:
        if not isinstance(data, BoardImport):
            raise ValidationError("Import requires a BoardImport value")
        board = _build_board(data)
        if not self.core.is_allowed(user_id, board, Permission.IMPORT_BOARD):
            raise PermissionError("User lacks permission to import this board")
        # Restore validates historical state; capacity may legitimately already be exceeded.
        snapshot = snapshot_board(board)
        try:
            restore_board(snapshot)
        except InvalidPersistenceStateError as error:
            raise ValidationError(str(error)) from error
        event = self.core.event_factory.create(
            "board.imported",
            board.id,
            "board",
            user_id,
            {"card_count": len(board.cards)},
        )
        event = replace(event, correlation_id=event.id)
        saved = self.core.unit_of_work.save(snapshot, (event,), expected_version=0)
        return restore_board(saved)
