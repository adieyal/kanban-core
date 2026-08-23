"""Board administration service for managing boards and columns."""

from __future__ import annotations

import copy
from dataclasses import replace
from typing import Any

from ..events import (
    BOARD_CREATED,
    BOARD_DELETED,
    BOARD_UPDATED,
    COLUMN_CREATED,
    COLUMN_DELETED,
    COLUMN_UPDATED,
    Event,
)
from ..exceptions import NotFoundError, ValidationError
from ..models import Board, Column, ColumnPolicy
from ..repositories import restore_board, snapshot_board
from ..permissions import Permission
from .core import _KanbanServiceCore


class BoardAdminService:
    """Service for board and column administration operations."""

    def __init__(self, core: _KanbanServiceCore):
        self.core = core

    def _reindex_columns(self, board: Board) -> None:
        """Re-number column.position to 0..n-1 in display order."""
        for pos, col in enumerate(
            sorted(board.columns.values(), key=lambda c: c.position)
        ):
            col.position = pos

    def create_board(
        self, name: str, owner_id: str, columns: list[str] | None = None
    ) -> Board:
        if not name.strip():
            raise ValidationError("Board name must not be empty")
        if not owner_id.strip():
            raise ValidationError("Board owner must not be empty")

        col_names = columns if columns is not None else ["To Do", "In Progress", "Done"]
        if any(not column_name.strip() for column_name in col_names):
            raise ValidationError("Column names must not be empty")
        if len(set(col_names)) != len(col_names):
            raise ValidationError("Column names must be unique")

        board_id = self.core.id_factory()
        now = self.core.clock()

        board = Board(
            id=board_id,
            name=name,
            owner_id=owner_id,
            team_ids={owner_id},
            created_at=now,
            updated_at=now,
        )

        for pos, col_name in enumerate(col_names):
            col_id = self.core.id_factory()
            board.columns[col_id] = Column(
                id=col_id,
                board_id=board_id,
                name=col_name,
                position=pos,
            )

        evt = self.core.event_factory.create(
            BOARD_CREATED, board.id, "board", owner_id, {}
        )
        evt = replace(evt, correlation_id=evt.id)
        saved = self.core.unit_of_work.save(snapshot_board(board), (evt,))
        return restore_board(saved)

    def update_column(
        self, board_id: str, column_id: str, user_id: str, **kwargs: Any
    ) -> Column:
        allowed = {"name", "color", "position", "policy"}
        unknown = set(kwargs) - allowed
        if unknown:
            raise ValidationError(f"Unsupported column fields: {sorted(unknown)}")

        def action(board: Board) -> tuple[Column, list[Event]]:
            column = board.columns.get(column_id)
            if not column:
                raise NotFoundError("Column not found")

            before = copy.deepcopy(column)

            # primitive fields
            if "name" in kwargs:
                new_name = str(kwargs["name"])
                if not new_name.strip():
                    raise ValidationError("Column name must not be empty")
                if any(
                    item.id != column.id and item.name == new_name
                    for item in board.columns.values()
                ):
                    raise ValidationError(f"Column name '{new_name}' already exists")
                column.name = new_name
            if "color" in kwargs:
                column.color = kwargs["color"]

            # position change
            if "position" in kwargs and kwargs["position"] is not None:
                new_pos = int(kwargs["position"])
                ordered = sorted(board.columns.values(), key=lambda item: item.position)
                ordered.remove(column)
                if new_pos < 0 or new_pos > len(ordered):
                    raise ValidationError(
                        f"Position must be between 0 and {len(ordered)}, got {new_pos}"
                    )
                ordered.insert(new_pos, column)
                for index, item in enumerate(ordered):
                    item.position = index

            # policy changes
            if "policy" in kwargs:
                pol = kwargs["policy"]
                if isinstance(pol, dict):
                    policy_fields = {"wip_limit"}
                    unknown_policy = set(pol) - policy_fields
                    if unknown_policy:
                        raise ValidationError(
                            f"Unsupported policy fields: {sorted(unknown_policy)}"
                        )
                    for k, v in pol.items():
                        setattr(column.policy, k, v)
                elif isinstance(pol, ColumnPolicy):
                    column.policy = pol
                else:
                    raise ValidationError("Unsupported policy payload")

            if column == before:
                return column, []
            board.updated_at = self.core.clock()

            evt = self.core.event_factory.create(
                COLUMN_UPDATED,
                column.id,
                "column",
                user_id,
                {"before": before.__dict__, "after": column.__dict__},
            )
            return column, [evt]

        updated, _ = self.core._execute_transaction(
            board_id, user_id, Permission.EDIT_COLUMN, action
        )
        return updated

    def create_column(
        self, board_id: str, user_id: str, name: str, position: int | None = None
    ) -> Column:
        if not name.strip():
            raise ValidationError("Column name must not be empty")

        def action(board: Board) -> tuple[Column, list[Event]]:
            if any(c.name == name for c in board.columns.values()):
                raise ValidationError(f"Column name '{name}' already exists")

            pos = position if position is not None else len(board.columns)
            if pos < 0 or pos > len(board.columns):
                raise ValidationError(
                    f"Position must be between 0 and {len(board.columns)}, got {pos}"
                )
            for col in board.columns.values():
                if col.position >= pos:
                    col.position += 1

            col_id = self.core.id_factory()
            new_col = Column(id=col_id, board_id=board.id, name=name, position=pos)
            board.columns[col_id] = new_col
            self._reindex_columns(board)
            board.updated_at = self.core.clock()

            evt = self.core.event_factory.create(
                COLUMN_CREATED,
                col_id,
                "column",
                user_id,
                {"name": name, "position": pos},
            )
            return new_col, [evt]

        col, _ = self.core._execute_transaction(
            board_id, user_id, Permission.CREATE_COLUMN, action
        )
        return col

    def delete_column(self, board_id: str, column_id: str, user_id: str) -> None:
        def action(board: Board) -> tuple[None, list[Event]]:
            column = board.columns.get(column_id)
            if not column:
                raise NotFoundError("Column not found")
            if column.card_ids:
                raise ValidationError("Cannot delete a non-empty column")

            del board.columns[column_id]
            self._reindex_columns(board)
            board.updated_at = self.core.clock()

            evt = self.core.event_factory.create(
                COLUMN_DELETED, column_id, "column", user_id, {}
            )
            return None, [evt]

        self.core._execute_transaction(
            board_id, user_id, Permission.DELETE_COLUMN, action
        )

    def update_board(self, board_id: str, user_id: str, **kwargs: Any) -> Board:
        editable = {"name", "description", "owner_id", "team_ids"}
        unknown = set(kwargs) - editable
        if unknown:
            raise ValidationError(f"Unsupported board fields: {sorted(unknown)}")

        def action(board: Board) -> tuple[Board, list[Event]]:
            changes: dict[str, object] = {}
            for k, v in kwargs.items():
                if k == "name" and not str(v).strip():
                    raise ValidationError("Board name must not be empty")
                if k == "owner_id" and (not isinstance(v, str) or not v.strip()):
                    raise ValidationError("Board owner must not be empty")
                if k == "team_ids" and not isinstance(v, set):
                    v = set(v)
                setattr(board, k, v)
                changes[k] = v

            if not changes:
                return board, []

            board.updated_at = self.core.clock()
            evt = self.core.event_factory.create(
                BOARD_UPDATED, board.id, "board", user_id, {"changes": changes}
            )
            return board, [evt]

        _, committed = self.core._execute_transaction(
            board_id, user_id, Permission.EDIT_BOARD, action
        )
        return committed

    def delete_board(self, board_id: str, user_id: str) -> None:
        board = self.core.get_board_and_check_permission(
            board_id, user_id, Permission.DELETE_BOARD
        )
        evt = self.core.event_factory.create(
            BOARD_DELETED,
            board_id,
            "board",
            user_id,
            {},
        )
        evt = replace(evt, correlation_id=evt.id)
        self.core.unit_of_work.delete(board_id, (evt,), expected_version=board.version)
