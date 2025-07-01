"""Card workflow service for managing card lifecycle operations."""

from __future__ import annotations

import copy
from typing import Any

from ..events import CARD_CREATED, CARD_DELETED, CARD_UPDATED
from ..exceptions import NotFoundError, ValidationError
from ..models import Board, Card
from ..permissions import Permission
from ..repositories import snapshot_board
from .automation import AutomationContext
from .core import _KanbanServiceCore


class CardWorkflowService:
    """
    All card–lifecycle operations live here.
    Every public method wraps its mutation inside
    `_execute_transaction`, so optimistic‐locking, events,
    automations and permission checks remain consistent.
    """

    def __init__(self, core: _KanbanServiceCore):
        self.core = core

    def _validate_custom_fields(self, board: Board, custom: dict[str, Any]):
        for field_key, value in custom.items():
            if field_key not in board.custom_fields:
                raise ValidationError(f"Unknown custom field '{field_key}'")
            board.custom_fields[field_key].validate(value)

    def create_card(
        self, board_id: str, column_id: str, title: str, user_id: str, **kwargs
    ) -> Card:
        def action(board: Board, ctx: AutomationContext):
            if column_id not in board.columns:
                raise NotFoundError("Column not found")

            self._validate_custom_fields(board, kwargs.get("custom_fields", {}))

            col = board.columns[column_id]
            # enforce entry criteria & WIP
            ok, reason = col.can_accept_card(Card(id="tmp", column_id=column_id), True)
            if not ok:
                raise ValidationError(reason)

            card_id = self.core.id_factory()
            new = Card(
                id=card_id,
                column_id=column_id,
                title=title,
                position=len(col.card_ids),
                created_at=self.core.clock(),
                entered_column_at=self.core.clock(),
                **kwargs,
            )
            board.cards[card_id] = new
            col.card_ids.append(card_id)

            evt = self.core.event_factory.create(
                CARD_CREATED, card_id, "card", user_id, {}
            )
            return new, [evt]

        card, _ = self.core._execute_transaction(
            board_id, user_id, Permission.CREATE_CARD, action
        )
        return card

    def update_card(self, board_id: str, card_id: str, user_id: str, **changes) -> Card:
        """
        Supports changing primitive fields and/or moving the card
        by passing `column_id` and optional `position`.
        """

        def action(board: Board, ctx: AutomationContext):
            if card_id not in board.cards:
                raise NotFoundError("Card not found")

            card = board.cards[card_id]
            before = copy.deepcopy(card)  # cheap structural copy

            # move?
            new_col_id: str | None = changes.pop("column_id", None)
            new_pos: int | None = changes.pop("position", None)
            if new_col_id and new_col_id != card.column_id:
                self.core._internal_move(board, card_id, new_col_id, new_pos)

            # simple attribute updates
            for attr, val in changes.items():
                if attr == "custom_fields":
                    self._validate_custom_fields(board, val)
                setattr(card, attr, val)
            card.updated_at = self.core.clock()

            evt = self.core.event_factory.create(
                CARD_UPDATED,
                card_id,
                "card",
                user_id,
                {"before": before.to_dict(), "after": card.to_dict()},
            )
            return card, [evt]

        card, _ = self.core._execute_transaction(
            board_id, user_id, Permission.EDIT_CARD, action
        )
        return card

    def move_card(
        self,
        board_id: str,
        card_id: str,
        to_column_id: str,
        position: int | None,
        user_id: str,
    ) -> Card:
        def action(board: Board, ctx: AutomationContext):
            moved = self.core._internal_move(board, card_id, to_column_id, position)
            return moved, []  # event already published inside helper

        moved, _ = self.core._execute_transaction(
            board_id, user_id, Permission.MOVE_CARD, action
        )
        return moved

    def delete_card(self, board_id: str, card_id: str, user_id: str) -> None:
        def action(board: Board, ctx: AutomationContext):
            if card_id not in board.cards:
                raise NotFoundError("Card not found")
            card = board.cards.pop(card_id)
            # drop from its column
            col = board.columns.get(card.column_id)
            if col and card_id in col.card_ids:
                col.card_ids.remove(card_id)

            evt = self.core.event_factory.create(
                CARD_DELETED, card_id, "card", user_id, {}
            )
            return None, [evt]

        self.core._execute_transaction(
            board_id, user_id, Permission.DELETE_CARD, action
        )

    def block_card_dependency(
        self, board_id: str, blocking_card_id: str, card_to_block_id: str, user_id: str
    ):
        def action(board: Board, ctx: AutomationContext):
            blocker = board.cards.get(blocking_card_id)
            blocked = board.cards.get(card_to_block_id)
            if not blocker or not blocked:
                raise NotFoundError("One or both cards not found")

            blocker.blocks.add(card_to_block_id)
            blocked.blocked_by.add(blocking_card_id)

            evt = self.core.event_factory.create(
                "card.blocked",
                card_to_block_id,
                "card",
                user_id,
                {"blocker_id": blocking_card_id},
            )
            return None, [evt]

        self.core._execute_transaction(board_id, user_id, Permission.EDIT_CARD, action)

    def unblock_card_dependency(
        self,
        board_id: str,
        blocking_card_id: str,
        card_to_unblock_id: str,
        user_id: str,
    ):
        def action(board: Board, ctx: AutomationContext):
            blocker = board.cards.get(blocking_card_id)
            blocked = board.cards.get(card_to_unblock_id)
            if not blocker or not blocked:
                raise NotFoundError("One or both cards not found")

            blocker.blocks.discard(card_to_unblock_id)
            blocked.blocked_by.discard(blocking_card_id)

            evt = self.core.event_factory.create(
                "card.unblocked",
                card_to_unblock_id,
                "card",
                user_id,
                {"blocker_id": blocking_card_id},
            )
            return None, [evt]

        self.core._execute_transaction(board_id, user_id, Permission.EDIT_CARD, action)