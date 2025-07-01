from __future__ import annotations

import copy
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .events import (
    BOARD_CREATED,
    BOARD_DELETED,
    BOARD_UPDATED,
    CARD_BLOCKED,
    CARD_CREATED,
    CARD_DELETED,
    CARD_MOVED,
    CARD_UNBLOCKED,
    CARD_UPDATED,
    COLUMN_CREATED,
    COLUMN_DELETED,
    COLUMN_UPDATED,
    Event,
    EventBus,
)
from .exceptions import (
    Clock,
    IDFactory,
    KanbanError,
    NotFoundError,
    PermissionError,
    ValidationError,
)
from .models import Board, Card, Column, ColumnPolicy
from .permissions import Permission, PermissionChecker
from .repositories import IKanbanRepository, snapshot_board

# ============= PLUGGABLE INTERFACES =============


# B-4: Interface for pluggable search strategies
class ICardSearcher(ABC):
    @abstractmethod
    def search(self, board: Board, **filters) -> list[Card]:
        """Search for cards within a board based on filter criteria."""
        pass


class InMemoryCardSearcher(ICardSearcher):
    """Default, in-memory search implementation."""

    def search(self, board: Board, **filters) -> list[Card]:
        results = list(board.cards.values())
        if text := filters.get("text"):
            text_lower = text.lower()
            results = [
                c
                for c in results
                if text_lower in c.title.lower() or text_lower in c.description.lower()
            ]
        if labels := filters.get("labels"):
            required_labels = set(labels)
            results = [
                c
                for c in results
                if required_labels.issubset(c.custom_fields.get("labels", set()))
            ]
        if assignee_ids := filters.get("assignee_ids"):
            results = [c for c in results if assignee_ids.intersection(c.assignee_ids)]
        if (is_blocked := filters.get("is_blocked")) is not None:
            results = [c for c in results if c.is_blocked() == is_blocked]
        return results


# B-5: Interface for pluggable automation execution strategies
class IAutomationRunner(ABC):
    @abstractmethod
    def run(
        self,
        board: Board,
        event: Event,
        service_core: _KanbanServiceCore,
        ctx: AutomationContext,
    ) -> bool:
        """
        Execute automation rules.
        Returns a boolean 'dirty' flag indicating if the board was modified.
        """
        pass


@dataclass
class AutomationContext:
    processed_event_ids: set[str] = field(default_factory=set)


class SyncAutomationRunner(IAutomationRunner):
    MAX_CHAIN = 25  # sane default

    def run(
        self,
        board: Board,
        event: Event,
        service_core: _KanbanServiceCore,
        ctx: AutomationContext,
    ) -> bool:
        if len(ctx.processed_event_ids) >= self.MAX_CHAIN:
            raise KanbanError("Automation chain limit exceeded")

        if event.id in ctx.processed_event_ids:
            return False
        ctx.processed_event_ids.add(event.id)

        dirty = False
        for rule in filter(
            lambda r: r.enabled and r.trigger(event), board.automation_rules
        ):
            before = snapshot_board(board)
            rule.action(event, board, service_core, ctx)
            dirty |= board != before
        return dirty


# ============= SERVICE LAYER ARCHITECTURE =============


## FIX 5.1.1: New EventFactory to centralize event creation.
class EventFactory:
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


## FIX 5.1.2: A private core context for dependencies and transactions.
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
            CARD_MOVED,
            card_id,
            "card",
            None,
            {"from_column_id": from_col.id, "to_column_id": to_col.id},
        )
        self.event_bus.publish(evt)
        return card


## FIX 5.1.3: A dedicated service for card lifecycle management.
class CardWorkflowService:
    """
    All card–lifecycle operations live here.
    Every public method wraps its mutation inside
    `_execute_transaction`, so optimistic‐locking, events,
    automations and permission checks remain consistent.
    """

    # ---------- construction ----------
    def __init__(self, core: _KanbanServiceCore):
        self.core = core

    # ---------- helpers ----------
    def _validate_custom_fields(self, board: Board, custom: dict[str, Any]):
        for field_key, value in custom.items():
            if field_key not in board.custom_fields:
                raise ValidationError(f"Unknown custom field '{field_key}'")
            board.custom_fields[field_key].validate(value)

    # ---------- create ----------
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

    # ---------- update ----------
    def update_card(self, board_id: str, card_id: str, user_id: str, **changes) -> Card:
        """
        Supports changing primitive fields and/or moving the card
        by passing `column_id` and optional `position`.
        """

        def action(board: Board, ctx: AutomationContext):
            if card_id not in board.cards:
                raise NotFoundError("Card not found")

            card = board.cards[card_id]
            before = snapshot_board(card)  # cheap structural copy

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

    # ---------- move ----------
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

    # ---------- delete ----------
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

    # ---------- block / unblock ----------
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
                CARD_BLOCKED,
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
                CARD_UNBLOCKED,
                card_to_unblock_id,
                "card",
                user_id,
                {"blocker_id": blocking_card_id},
            )
            return None, [evt]

        self.core._execute_transaction(board_id, user_id, Permission.EDIT_CARD, action)


## FIX 5.1.4: A dedicated service for board administration.
class BoardAdminService:
    def __init__(self, core: _KanbanServiceCore):
        self.core = core

    # ---------- helpers ----------
    def _reindex_columns(self, board: Board):
        """Re-number column.position to 0..n-1 in display order."""
        for pos, col in enumerate(
            sorted(board.columns.values(), key=lambda c: c.position)
        ):
            col.position = pos

    # ---------- create board ----------
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

    # ---------- column update ----------
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

    # ---------- column create ----------
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

    # ---------- column delete ----------
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

    # ---------- board update ----------
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

    # ---------- board delete ----------
    def delete_board(self, board_id: str, user_id: str) -> None:
        self.core.get_board_and_check_permission(
            board_id, user_id, Permission.DELETE_BOARD
        )
        self.core.repository.delete(board_id)
        evt = self.core.event_factory.create(
            BOARD_DELETED, board_id, "board", user_id, {}
        )
        self.core.event_bus.publish(evt)
