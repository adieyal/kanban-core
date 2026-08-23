"""Core service infrastructure for the kanban library."""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import replace
from typing import TypeVar

from ..events import Event
from ..exceptions import (
    Clock,
    IDFactory,
    NotFoundError,
    PermissionError,
    ValidationError,
)
from ..models import Board, Card
from ..permissions import Permission, PermissionContext, PermissionPolicy
from ..policies import (
    AllowAllWorkflowPolicy,
    CardMovePolicyContext,
    CardPolicyContext,
    WorkflowPolicy,
)
from ..repositories import KanbanRepository, restore_board, snapshot_board
from ..unit_of_work import KanbanUnitOfWork
from .automation import (
    AutomationCardFacts,
    AutomationColumnFacts,
    AutomationFacts,
    AutomationRunner,
    MoveCardAction,
)
from .search import CardSearcher, SearchCard, SearchContext

T = TypeVar("T")
_MAX_AUTOMATION_CHAIN = 25



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
        data: dict[str, object],
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
    """Shared dependencies plus the single transaction path."""

    def __init__(
        self,
        repository: KanbanRepository,
        unit_of_work: KanbanUnitOfWork,
        permission_checker: PermissionPolicy,
        searcher: CardSearcher,
        automation_runner: AutomationRunner,
        clock: Clock,
        id_factory: IDFactory,
        workflow_policy: WorkflowPolicy | None = None,
    ):
        self.repository = repository
        self.permission_checker = permission_checker
        self.searcher = searcher
        self.automation_runner = automation_runner
        self.clock = clock
        self.id_factory = id_factory
        self.event_factory = EventFactory(clock, id_factory)
        self.unit_of_work = unit_of_work
        self.workflow_policy = workflow_policy or AllowAllWorkflowPolicy()

    @staticmethod
    def policy_context(board: Board, card: Card, user_id: str) -> CardPolicyContext:
        return CardPolicyContext(
            board_id=board.id,
            user_id=user_id,
            card_id=card.id,
            column_id=board.column_for_card(card.id).id,
            title=card.title,
            description=card.description,
            assignee_ids=frozenset(card.assignee_ids),
            due_date=card.due_date,
            size=card.size,
            archived=card.archived,
        )

    def automation_facts(self, board: Board) -> AutomationFacts:
        return AutomationFacts(
            cards=tuple(
                AutomationCardFacts(
                    card.id,
                    board.column_for_card(card.id).id,
                    card.title,
                    card.due_date,
                    card.archived,
                )
                for card in sorted(board.cards.values(), key=lambda item: item.id)
            ),
            columns=tuple(
                AutomationColumnFacts(column.id, column.name)
                for column in board.get_columns_ordered()
            ),
            now=self.clock(),
        )

    @staticmethod
    def permission_context(board: Board) -> PermissionContext:
        owner_id = board.owner_id
        if owner_id is None:
            raise ValidationError("Board owner must be non-empty")
        return PermissionContext(
            board_id=board.id,
            owner_id=owner_id,
            team_ids=frozenset(board.team_ids),
        )

    @staticmethod
    def search_context(board: Board) -> SearchContext:
        return SearchContext(
            cards=tuple(
                SearchCard(
                    card.id,
                    card.title,
                    card.description,
                    frozenset(card.assignee_ids),
                    card.is_blocked(),
                )
                for card in board.cards.values()
            )
        )

    def is_allowed(self, user_id: str, board: Board, permission: Permission) -> bool:
        return self.permission_checker.has_permission(
            user_id, self.permission_context(board), permission
        )

    def get_board_and_check_permission(
        self, board_id: str, user_id: str, permission: Permission
    ) -> Board:
        snapshot = self.repository.get(board_id)
        if snapshot is None:
            raise NotFoundError(f"Board '{board_id}' not found.")
        board = restore_board(snapshot)
        if not self.is_allowed(user_id, board, permission):
            raise PermissionError(
                f"User '{user_id}' lacks permission {permission.name} for board '{board_id}'."
            )
        return board

    def _execute_transaction(
        self,
        board_id: str,
        user_id: str,
        permission: Permission,
        action: Callable[[Board], tuple[T, list[Event]]],
    ) -> tuple[T, Board]:
        board = self.get_board_and_check_permission(board_id, user_id, permission)
        original_version = board.version
        before = copy.deepcopy(board)

        action_result, primary_events = action(board)
        dirty = board != before

        correlation_id = next(
            (event.correlation_id or event.id for event in primary_events), None
        )
        events = [
            replace(event, correlation_id=event.correlation_id or correlation_id)
            for event in primary_events
        ]

        event_index = 0
        while event_index < len(events):
            if event_index >= _MAX_AUTOMATION_CHAIN:
                raise ValidationError("Automation chain limit exceeded")
            trigger = events[event_index]
            event_index += 1
            for requested in self.automation_runner.evaluate(
                trigger, self.automation_facts(board)
            ):
                generated = self._apply_automation_action(board, requested, user_id)
                if generated is None:
                    continue
                dirty = True
                events.append(
                    replace(
                        generated,
                        correlation_id=generated.correlation_id
                        or trigger.correlation_id
                        or trigger.id,
                        causation_id=generated.causation_id or trigger.id,
                    )
                )

        if dirty:
            saved = self.unit_of_work.save(
                snapshot_board(board),
                tuple(events),
                expected_version=original_version,
            )
            final_board = restore_board(saved)
        else:
            final_board = board
            if events:
                self.unit_of_work.emit(tuple(events), board.version)

        return action_result, final_board

    def _apply_automation_action(
        self, board: Board, action: object, user_id: str
    ) -> Event | None:
        if isinstance(action, MoveCardAction):
            _, event = self._internal_move(
                board, action.card_id, action.to_column_id, user_id=user_id
            )
            return event

        raise ValidationError("Unsupported automation action")

    def _internal_move(
        self,
        board: Board,
        card_id: str,
        to_column_id: str,
        position: int | None = None,
        user_id: str | None = None,
    ) -> tuple[Card, Event | None]:
        card = board.cards.get(card_id)
        if card is None:
            raise NotFoundError("Card not found")
        from_col = board.column_for_card(card_id)
        to_col = board.columns.get(to_column_id)
        if to_col is None:
            raise NotFoundError("Target column not found")

        is_new_entry = from_col.id != to_col.id
        ok, reason = to_col.can_accept_card(is_new_entry=is_new_entry)
        if not ok:
            raise ValidationError(reason)

        current_position = from_col.card_ids.index(card_id)
        if not is_new_entry and (position is None or position == current_position):
            return card, None

        target_size = len(to_col.card_ids) - (0 if is_new_entry else 1)
        insert_at = target_size if position is None else position
        if insert_at < 0 or insert_at > target_size:
            raise ValidationError(
                f"Position must be between 0 and {target_size}, got {insert_at}"
            )

        self.workflow_policy.validate_move(
            CardMovePolicyContext(
                card=self.policy_context(board, card, user_id or ""),
                from_column_id=from_col.id,
                to_column_id=to_col.id,
                position=insert_at,
            )
        )

        from_col.card_ids.remove(card_id)
        to_col.card_ids.insert(insert_at, card_id)
        board.updated_at = self.clock()

        return card, self.event_factory.create(
            "card.moved",
            card_id,
            "card",
            user_id,
            {
                "from_column_id": from_col.id,
                "to_column_id": to_col.id,
                "position": insert_at,
            },
        )
