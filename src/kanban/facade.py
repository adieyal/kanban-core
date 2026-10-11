from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from .attributes import freeze_attributes
from .events import Event
from .exceptions import (
    Clock,
    IDFactory,
    ValidationError,
    require_aware_datetime,
    utc_clock,
    uuid4_factory,
)
from .imports import BoardImport
from .models import Board, Card, Column, WipGroup
from .permissions import Permission, PermissionPolicy, SimplePermissionPolicy
from .policies import WorkflowPolicy
from .repositories import KanbanRepository, restore_board
from .services import (
    BoardAdminService,
    CardSearcher,
    CardWorkflowService,
    InMemoryCardSearcher,
    SyncAutomationRunner,
    _KanbanServiceCore,
)
from .services.board_import import BoardImportService
from .services.core import _TickBatch
from .spi.automation import AutomationRunner
from .unit_of_work import KanbanUnitOfWork


@dataclass(frozen=True, slots=True)
class TickResult:
    """Initial tick actions processed or deferred by the requested batch limit."""

    processed_card_ids: tuple[str, ...]
    deferred_card_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CardView:
    id: str
    column_id: str
    title: str
    description: str
    position: int
    blocked_by: frozenset[str]
    blocks: frozenset[str]
    assignee_ids: frozenset[str]
    due_date: datetime | None
    size: float | None
    archived: bool
    attributes: Mapping[str, object] = field(default_factory=dict)
    created_at: datetime | None = None
    entered_column_at: datetime | None = None
    blocked_reason: str | None = None
    blocked_at: datetime | None = None
    is_blocked: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "attributes", freeze_attributes(self.attributes))


@dataclass(frozen=True, slots=True)
class ColumnView:
    id: str
    name: str
    position: int
    card_ids: tuple[str, ...]
    color: str | None
    wip_limit: int | None
    max_age: timedelta | None = None


@dataclass(frozen=True, slots=True)
class AgingCardsView:
    """Over-age cards, oldest first, and cards whose column-entry age is unknown."""

    cards: tuple[CardView, ...]
    unknown_age_cards: tuple[CardView, ...]


@dataclass(frozen=True, slots=True)
class BoardView:
    id: str
    version: int
    name: str
    description: str
    columns: tuple[ColumnView, ...]
    cards: tuple[CardView, ...]
    created_at: datetime | None
    updated_at: datetime | None
    owner_id: str | None
    team_ids: frozenset[str]
    wip_groups: tuple[WipGroup, ...] = ()

    def column_named(self, name: str) -> ColumnView | None:
        return next((column for column in self.columns if column.name == name), None)

    def card(self, card_id: str) -> CardView | None:
        return next((card for card in self.cards if card.id == card_id), None)


def _card_view(card: Card, board: Board) -> CardView:
    column = board.column_for_card(card.id)
    return CardView(
        id=card.id,
        column_id=column.id,
        title=card.title,
        description=card.description,
        position=column.card_ids.index(card.id),
        blocked_by=frozenset(card.blocked_by),
        blocks=frozenset(card.blocks),
        assignee_ids=frozenset(card.assignee_ids),
        due_date=card.due_date,
        size=card.size,
        archived=card.archived,
        attributes=card.attributes,
        created_at=card.created_at,
        entered_column_at=card.entered_column_at,
        blocked_reason=card.blocked_reason,
        blocked_at=card.blocked_at,
        is_blocked=card.is_blocked(),
    )


def _column_view(column: Column) -> ColumnView:
    return ColumnView(
        id=column.id,
        name=column.name,
        position=column.position,
        card_ids=tuple(column.card_ids),
        color=column.color,
        wip_limit=column.policy.wip_limit,
        max_age=column.policy.max_age,
    )


def _board_view(board: Board) -> BoardView:
    cards = [
        card
        for column in board.get_columns_ordered()
        for card in board.get_cards_in_column(column.id)
    ]
    return BoardView(
        id=board.id,
        version=board.version,
        name=board.name,
        description=board.description,
        columns=tuple(_column_view(column) for column in board.get_columns_ordered()),
        cards=tuple(_card_view(card, board) for card in cards),
        created_at=board.created_at,
        updated_at=board.updated_at,
        owner_id=board.owner_id,
        team_ids=frozenset(board.team_ids),
        wip_groups=board.wip_groups,
    )


class KanbanFacade:
    """The complete public business capability surface for kanban-core."""

    def __init__(
        self,
        repository: KanbanRepository,
        unit_of_work: KanbanUnitOfWork,
        permission_checker: PermissionPolicy | None = None,
        searcher: CardSearcher | None = None,
        automation_runner: AutomationRunner | None = None,
        clock: Clock | None = None,
        id_factory: IDFactory | None = None,
        workflow_policy: WorkflowPolicy | None = None,
    ) -> None:
        core = _KanbanServiceCore(
            repository=repository,
            unit_of_work=unit_of_work,
            permission_checker=permission_checker or SimplePermissionPolicy(),
            searcher=searcher or InMemoryCardSearcher(),
            automation_runner=automation_runner or SyncAutomationRunner(),
            clock=clock or utc_clock,
            id_factory=id_factory or uuid4_factory,
            workflow_policy=workflow_policy,
        )
        self._core = core
        self._admin = BoardAdminService(core)
        self._cards = CardWorkflowService(core)
        self._imports = BoardImportService(core)

    def import_board(self, user_id: str, data: BoardImport) -> BoardView:
        return _board_view(self._imports.import_board(user_id, data))

    def create_board(
        self, user_id: str, name: str, columns: list[str] | None = None
    ) -> BoardView:
        return _board_view(self._admin.create_board(name, user_id, columns))

    def get_board(self, user_id: str, board_id: str) -> BoardView:
        board = self._core.get_board_and_check_permission(
            board_id, user_id, Permission.VIEW_BOARD
        )
        return _board_view(board)

    def list_boards(self, user_id: str) -> list[BoardView]:
        boards = [restore_board(item) for item in self._core.repository.list_all()]
        return [
            _board_view(board)
            for board in boards
            if self._core.is_allowed(user_id, board, Permission.VIEW_BOARD)
        ]

    def update_board(self, user_id: str, board_id: str, **changes: Any) -> BoardView:
        return _board_view(self._admin.update_board(board_id, user_id, **changes))

    def delete_board(self, user_id: str, board_id: str) -> None:
        self._admin.delete_board(board_id, user_id)

    def add_column(
        self,
        user_id: str,
        board_id: str,
        name: str,
        position: int | None = None,
    ) -> ColumnView:
        return _column_view(
            self._admin.create_column(board_id, user_id, name, position)
        )

    def update_column(
        self, user_id: str, board_id: str, column_id: str, **changes: Any
    ) -> ColumnView:
        return _column_view(
            self._admin.update_column(board_id, column_id, user_id, **changes)
        )

    def delete_column(self, user_id: str, board_id: str, column_id: str) -> None:
        self._admin.delete_column(board_id, column_id, user_id)

    def add_card(
        self,
        user_id: str,
        board_id: str,
        column_id: str,
        title: str,
        **fields: Any,
    ) -> CardView:
        card = self._cards.create_card(board_id, column_id, title, user_id, **fields)
        board = self._core.get_board_and_check_permission(
            board_id, user_id, Permission.VIEW_BOARD
        )
        return _card_view(card, board)

    def update_card(
        self, user_id: str, board_id: str, card_id: str, **changes: Any
    ) -> CardView:
        card = self._cards.update_card(board_id, card_id, user_id, **changes)
        board = self._core.get_board_and_check_permission(
            board_id, user_id, Permission.VIEW_BOARD
        )
        return _card_view(card, board)

    def move_card(
        self,
        user_id: str,
        board_id: str,
        card_id: str,
        to_column_id: str,
        position: int | None = None,
    ) -> CardView:
        card = self._cards.move_card(board_id, card_id, to_column_id, position, user_id)
        board = self._core.get_board_and_check_permission(
            board_id, user_id, Permission.VIEW_BOARD
        )
        return _card_view(card, board)

    def delete_card(self, user_id: str, board_id: str, card_id: str) -> None:
        self._cards.delete_card(board_id, card_id, user_id)

    def block_card(
        self,
        user_id: str,
        board_id: str,
        card_to_block_id: str,
        blocking_card_id: str,
    ) -> None:
        self._cards.block_card_dependency(
            board_id, blocking_card_id, card_to_block_id, user_id
        )

    def unblock_card(
        self,
        user_id: str,
        board_id: str,
        card_to_unblock_id: str,
        blocking_card_id: str,
    ) -> None:
        self._cards.unblock_card_dependency(
            board_id, blocking_card_id, card_to_unblock_id, user_id
        )

    def block_card_external(
        self, user_id: str, board_id: str, card_id: str, reason: str
    ) -> None:
        if reason is None:
            raise ValidationError("External block reason must not be empty")
        self._cards.set_external_block(board_id, card_id, user_id, reason)

    def unblock_card_external(self, user_id: str, board_id: str, card_id: str) -> None:
        self._cards.set_external_block(board_id, card_id, user_id, None)

    def search_cards(
        self, user_id: str, board_id: str, **filters: Any
    ) -> list[CardView]:
        board = self._core.get_board_and_check_permission(
            board_id, user_id, Permission.VIEW_BOARD
        )
        card_ids = self._core.searcher.search(
            self._core.search_context(board), **filters
        )
        return [_card_view(board.cards[card_id], board) for card_id in card_ids]

    def tick(
        self, user_id: str, board_id: str, *, max_actions: int = 100
    ) -> TickResult:
        """Run a bounded batch of scheduled rules as one business operation."""
        if type(max_actions) is not int or max_actions <= 0:
            raise ValidationError("Tick max_actions must be a positive integer")
        batch = _TickBatch(max_actions)

        def action(board: Board) -> tuple[None, list[Event]]:
            event = self._core.event_factory.create(
                "board.tick", board.id, "board", user_id, {}
            )
            return None, [event]

        self._core._execute_transaction(
            board_id,
            user_id,
            Permission.MANAGE_AUTOMATION,
            action,
            tick_batch=batch,
        )
        return TickResult(
            tuple(batch.processed_card_ids), tuple(batch.deferred_card_ids)
        )

    def aging_cards(
        self, user_id: str, board_id: str, now: datetime | None = None
    ) -> AgingCardsView:
        """Query active cards strictly beyond their current column's age limit."""
        board = self._core.get_board_and_check_permission(
            board_id, user_id, Permission.VIEW_BOARD
        )
        query_time = (
            self._core.clock() if now is None else require_aware_datetime(now)
        ).astimezone(timezone.utc)
        aged: list[tuple[datetime, Card]] = []
        unknown: list[Card] = []
        for column in board.get_columns_ordered():
            if column.policy.max_age is None:
                continue
            for card in board.get_cards_in_column(column.id):
                if card.archived:
                    continue
                if card.entered_column_at is None:
                    unknown.append(card)
                else:
                    entered_at = card.entered_column_at.astimezone(timezone.utc)
                    if query_time - entered_at > column.policy.max_age:
                        aged.append((entered_at, card))
        aged.sort(key=lambda item: (item[0], item[1].id))
        unknown.sort(key=lambda card: card.id)
        return AgingCardsView(
            cards=tuple(_card_view(card, board) for _, card in aged),
            unknown_age_cards=tuple(_card_view(card, board) for card in unknown),
        )
