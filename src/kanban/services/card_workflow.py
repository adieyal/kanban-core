"""Card workflow service for managing card lifecycle operations."""

from __future__ import annotations

import copy
from typing import Any

from ..attributes import copy_attributes
from ..events import CARD_CREATED, CARD_DELETED, CARD_UPDATED, Event
from ..exceptions import NotFoundError, ValidationError
from ..models import Board, Card
from ..permissions import Permission
from .core import _KanbanServiceCore

_CREATE_FIELDS = {
    "description",
    "assignee_ids",
    "due_date",
    "size",
    "archived",
    "attributes",
}
_UPDATE_FIELDS = _CREATE_FIELDS | {"title"}


class CardWorkflowService:
    """
    All card–lifecycle operations live here.
    Every public method wraps its mutation inside
    `_execute_transaction`, so optimistic‐locking, events,
    automations and permission checks remain consistent.
    """

    def __init__(self, core: _KanbanServiceCore):
        self.core = core

    def create_card(
        self,
        board_id: str,
        column_id: str,
        title: str,
        user_id: str,
        **kwargs: Any,
    ) -> Card:
        unknown = set(kwargs) - _CREATE_FIELDS
        if unknown:
            raise ValidationError(f"Unsupported card fields: {sorted(unknown)}")
        if not title.strip():
            raise ValidationError("Card title must not be empty")

        def action(board: Board) -> tuple[Card, list[Event]]:
            if column_id not in board.columns:
                raise NotFoundError("Column not found")

            col = board.columns[column_id]
            card_id = self.core.id_factory()
            now = self.core.clock()
            candidate = Card(
                id=card_id,
                title=title,
                created_at=now,
                entered_column_at=now,
                **kwargs,
            )
            # enforce entry criteria & WIP
            ok, reason = col.can_accept_card(True)
            if not ok:
                raise ValidationError(reason)
            board.cards[card_id] = candidate
            col.card_ids.append(card_id)
            self.core.workflow_policy.validate_create(
                self.core.policy_context(board, candidate, user_id)
            )
            board.updated_at = now

            evt = self.core.event_factory.create(
                CARD_CREATED,
                card_id,
                "card",
                user_id,
                {"after": candidate.to_dict()},
                timestamp=now,
            )
            return candidate, [evt]

        card, _ = self.core._execute_transaction(
            board_id, user_id, Permission.CREATE_CARD, action
        )
        return card

    def update_card(
        self, board_id: str, card_id: str, user_id: str, **changes: Any
    ) -> Card:
        """Update editable card fields; movement is a separate capability."""

        unknown = set(changes) - _UPDATE_FIELDS
        if unknown:
            raise ValidationError(f"Unsupported card fields: {sorted(unknown)}")
        if "title" in changes and not str(changes["title"]).strip():
            raise ValidationError("Card title must not be empty")

        if "attributes" in changes:
            changes["attributes"] = copy_attributes(changes["attributes"])

        def action(board: Board) -> tuple[Card, list[Event]]:
            if card_id not in board.cards:
                raise NotFoundError("Card not found")

            card = board.cards[card_id]
            before = copy.deepcopy(card)  # cheap structural copy

            # simple attribute updates
            for attr, val in changes.items():
                setattr(card, attr, val)
            if card == before:
                return card, []
            self.core.workflow_policy.validate_update(
                self.core.policy_context(board, card, user_id)
            )
            board.updated_at = self.core.clock()

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
        def action(board: Board) -> tuple[Card, list[Event]]:
            moved, event = self.core._internal_move(
                board, card_id, to_column_id, position, user_id
            )
            return moved, [event] if event is not None else []

        moved, _ = self.core._execute_transaction(
            board_id, user_id, Permission.MOVE_CARD, action
        )
        return moved

    def delete_card(self, board_id: str, card_id: str, user_id: str) -> None:
        def action(board: Board) -> tuple[None, list[Event]]:
            if card_id not in board.cards:
                raise NotFoundError("Card not found")
            card = board.cards[card_id]
            self.core.workflow_policy.validate_delete(
                self.core.policy_context(board, card, user_id)
            )
            card = board.cards.pop(card_id)
            # drop from its column
            col = board.column_for_card(card_id)
            if col and card_id in col.card_ids:
                col.card_ids.remove(card_id)

            for other in board.cards.values():
                other.blocked_by.discard(card_id)
                other.blocks.discard(card_id)
            board.updated_at = self.core.clock()

            evt = self.core.event_factory.create(
                CARD_DELETED, card_id, "card", user_id, {}
            )
            return None, [evt]

        self.core._execute_transaction(
            board_id, user_id, Permission.DELETE_CARD, action
        )

    def block_card_dependency(
        self, board_id: str, blocking_card_id: str, card_to_block_id: str, user_id: str
    ) -> None:
        if blocking_card_id == card_to_block_id:
            raise ValidationError("A card cannot block itself")

        def action(board: Board) -> tuple[None, list[Event]]:
            blocker = board.cards.get(blocking_card_id)
            blocked = board.cards.get(card_to_block_id)
            if not blocker or not blocked:
                raise NotFoundError("One or both cards not found")

            if card_to_block_id in blocker.blocks:
                return None, []

            pending = [card_to_block_id]
            visited: set[str] = set()
            while pending:
                current = pending.pop()
                if current == blocking_card_id:
                    raise ValidationError("Card dependency would create a cycle")
                if current in visited:
                    continue
                visited.add(current)
                current_card = board.cards.get(current)
                if current_card is not None:
                    pending.extend(current_card.blocks)

            blocker.blocks.add(card_to_block_id)
            blocked.blocked_by.add(blocking_card_id)
            board.updated_at = self.core.clock()

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
    ) -> None:
        def action(board: Board) -> tuple[None, list[Event]]:
            blocker = board.cards.get(blocking_card_id)
            blocked = board.cards.get(card_to_unblock_id)
            if not blocker or not blocked:
                raise NotFoundError("One or both cards not found")

            if (
                card_to_unblock_id not in blocker.blocks
                and blocking_card_id not in blocked.blocked_by
            ):
                return None, []

            blocker.blocks.discard(card_to_unblock_id)
            blocked.blocked_by.discard(blocking_card_id)
            board.updated_at = self.core.clock()

            evt = self.core.event_factory.create(
                "card.unblocked",
                card_to_unblock_id,
                "card",
                user_id,
                {"blocker_id": blocking_card_id},
            )
            return None, [evt]

        self.core._execute_transaction(board_id, user_id, Permission.EDIT_CARD, action)

    def set_external_block(
        self, board_id: str, card_id: str, user_id: str, reason: str | None
    ) -> None:
        def action(board: Board) -> tuple[None, list[Event]]:
            event = self.core._internal_external_block(board, card_id, reason, user_id)
            return None, [event] if event is not None else []

        self.core._execute_transaction(board_id, user_id, Permission.EDIT_CARD, action)
