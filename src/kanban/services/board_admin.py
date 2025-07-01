"""Board administration service for managing boards and columns."""

from __future__ import annotations

import copy

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
from ..permissions import Permission
from .automation import AutomationContext
from .core import _KanbanServiceCore


class BoardAdminService:
    """Service for board and column administration operations."""

    def __init__(self, core: _KanbanServiceCore):
        self.core = core

    def _reindex_columns(self, board: Board):
        """Re-number column.position to 0..n-1 in display order."""
        for pos, col in enumerate(
            sorted(board.columns.values(), key=lambda c: c.position)
        ):
            col.position = pos

    def create_board(
        self, name: str, owner_id: str, columns: list[str] | None = None
    ) -> Board:
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

        # default columns
        col_names = columns or ["To Do", "In Progress", "Done"]
        for pos, col_name in enumerate(col_names):
            col_id = self.core.id_factory()
            board.columns[col_id] = Column(
                id=col_id,
                board_id=board_id,
                name=col_name,
                position=pos,
                is_done_column=(col_name.lower() == "done"),
            )

        board = self.core.repository.save(board)  # first persist

        # publish event
        evt = self.core.event_factory.create(
            BOARD_CREATED, board.id, "board", owner_id, {}
        )
        self.core.event_bus.publish(evt)
        return board

    def update_column(
        self, board_id: str, column_id: str, user_id: str, **kwargs
    ) -> Column:
        def action(board: Board, ctx: AutomationContext) -> tuple[Column, list[Event]]:
            column = board.columns.get(column_id)
            if not column:
                raise NotFoundError("Column not found")

            before = copy.deepcopy(column)

            # primitive fields
            if "name" in kwargs:
                column.name = kwargs["name"]
            if "is_done_column" in kwargs:
                column.is_done_column = bool(kwargs["is_done_column"])
            if "color" in kwargs:
                column.color = kwargs["color"]

            # position change
            if "position" in kwargs and kwargs["position"] is not None:
                new_pos = int(kwargs["position"])
                for col in board.columns.values():
                    if col.id != column.id and col.position >= new_pos:
                        col.position += 1
                column.position = new_pos
                self._reindex_columns(board)

            # policy changes
            if "policy" in kwargs:
                pol = kwargs["policy"]
                if isinstance(pol, dict):
                    for k, v in pol.items():
                        setattr(column.policy, k, v)
                elif isinstance(pol, ColumnPolicy):
                    column.policy = pol
                else:
                    raise ValidationError("Unsupported policy payload")

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
        def action(board: Board, ctx: AutomationContext):
            if any(c.name == name for c in board.columns.values()):
                raise ValidationError(f"Column name '{name}' already exists")

            pos = position if position is not None else len(board.columns)
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
        def action(board: Board, ctx: AutomationContext):
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

    def update_board(self, board_id: str, user_id: str, **kwargs) -> Board:
        editable = {"name", "description", "owner_id", "team_ids"}

        def action(board: Board, ctx: AutomationContext):
            changes = {}
            for k, v in kwargs.items():
                if k not in editable:
                    continue
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

        updated, _ = self.core._execute_transaction(
            board_id, user_id, Permission.EDIT_BOARD, action
        )
        return updated

    def delete_board(self, board_id: str, user_id: str) -> None:
        self.core.get_board_and_check_permission(
            board_id, user_id, Permission.DELETE_BOARD
        )
        self.core.repository.delete(board_id)
        evt = self.core.event_factory.create(
            BOARD_DELETED, board_id, "board", user_id, {}
        )
        self.core.event_bus.publish(evt)