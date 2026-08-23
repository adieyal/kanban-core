from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .exceptions import Clock, IDFactory, utc_clock, uuid4_factory
from .models import Board, Card, Column
from .permissions import Permission, PermissionPolicy, SimplePermissionPolicy
from .policies import WorkflowPolicy
from .repositories import KanbanRepository, restore_board
from .services import (
    AutomationRunner,
    BoardAdminService,
    CardSearcher,
    CardWorkflowService,
    InMemoryCardSearcher,
    SyncAutomationRunner,
    _KanbanServiceCore,
)
from .unit_of_work import KanbanUnitOfWork



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


@dataclass(frozen=True, slots=True)
class ColumnView:
    id: str
    name: str
    position: int
    card_ids: tuple[str, ...]
    color: str | None
    wip_limit: int | None


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
    )


def _column_view(column: Column) -> ColumnView:
    return ColumnView(
        id=column.id,
        name=column.name,
        position=column.position,
        card_ids=tuple(column.card_ids),
        color=column.color,
        wip_limit=column.policy.wip_limit,
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
        card = self._cards.move_card(
            board_id, card_id, to_column_id, position, user_id
        )
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
