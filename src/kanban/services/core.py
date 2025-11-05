"""Core service infrastructure for the kanban library."""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

from ..events import Event, EventBus
from ..exceptions import (
    Clock,
    IDFactory,
    NotFoundError,
    PermissionError,
    ValidationError,
)
from ..models import Board, Card
from ..permissions import Permission, PermissionChecker
from ..repositories import IKanbanRepository
from .automation import IAutomationRunner
from .automation_types import AutomationContext
from .search import ICardSearcher


class EventFactory:
    """Factory for creating events with consistent metadata."""

    def __init__(self, clock: Clock, id_factory: IDFactory):
        self.clock = clock
        self.id_factory = id_factory

    def create(
        self,
        event_type: str,
        entity_id: str,
        entity_type: str,
        user_id: str | None,
        data: dict,
    ) -> Event:
        return Event(
            type=event_type,
            entity_id=entity_id,
            entity_type=entity_type,
            user_id=user_id,
            data=data,
            id=self.id_factory(),
            timestamp=self.clock(),
        )


class _KanbanServiceCore:
    """Holds shared dependencies and the master transaction logic for all sub-services."""

    def __init__(
        self,
        repository: IKanbanRepository,
        event_bus: EventBus,
        permission_checker: PermissionChecker,
        searcher: ICardSearcher,
        automation_runner: IAutomationRunner,
        clock: Clock,
        id_factory: IDFactory,
    ):
        self.repository = repository
        self.event_bus = event_bus
        self.permission_checker = permission_checker
        self.searcher = searcher
        self.automation_runner = automation_runner
        self.clock = clock
        self.id_factory = id_factory
        self.event_factory = EventFactory(clock, id_factory)

    def get_board_and_check_permission(
        self, board_id: str, user_id: str, permission: Permission
    ) -> Board:
        board = self.repository.get(board_id)
        if not board:
            raise NotFoundError(f"Board '{board_id}' not found.")
        if not self.permission_checker.has_permission(user_id, board, permission):
            raise PermissionError(
                f"User '{user_id}' lacks permission {permission.name} for board '{board_id}'."
            )
        return board

    def _execute_transaction(
        self,
        board_id: str,
        user_id: str,
        permission: Permission,
        action: Callable[[Board, AutomationContext], tuple[Any, list[Event]]],
    ) -> tuple[Any, Board]:
        board = self.get_board_and_check_permission(board_id, user_id, permission)
        original_version = board.version
        # Make a copy *before* any mutations happen.
        board_before_action = copy.deepcopy(board)

        automation_context = AutomationContext()
        action_result, primary_events = action(board, automation_context)

        # Check if the primary action itself dirtied the board.
        board_was_modified_by_action = board != board_before_action

        board_was_modified_by_automation = False
        for event in primary_events:
            if self.automation_runner.run(board, event, self, automation_context):
                board_was_modified_by_automation = True

        # The save condition is now much cleaner and safer.
        if board_was_modified_by_action or board_was_modified_by_automation:
            final_board = self.repository.save(board, expected_version=original_version)
        else:
            final_board = board

        for event in primary_events:
            self.event_bus.publish(event)

        return action_result, final_board

    def _internal_move(
        self, board: Board, card_id: str, to_column_id: str, position: int | None = None
    ) -> Card:
        card = board.cards[card_id]
        from_col = board.columns[card.column_id]
        to_col = board.columns[to_column_id]

        ok, reason = to_col.can_accept_card(
            card, is_new_entry=card.column_id != to_column_id
        )
        if not ok:
            raise ValidationError(reason)

        # remove from old column
        if card_id in from_col.card_ids:
            from_col.card_ids.remove(card_id)

        # insert in new column
        insert_at = position if position is not None else len(to_col.card_ids)
        to_col.card_ids.insert(insert_at, card_id)
        card.column_id = to_column_id
        card.updated_at = self.clock()

        evt = self.event_factory.create(
            "card.moved",
            card_id,
            "card",
            None,
            {"from_column_id": from_col.id, "to_column_id": to_col.id},
        )
        self.event_bus.publish(evt)
        return card
