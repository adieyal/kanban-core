from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .commands import *
from .events import Event, EventBus
from .exceptions import Clock, IDFactory, NotFoundError, PermissionError
from .models import Board, Card, Column
from .permissions import Permission, PermissionChecker, SimplePermissionChecker
from .repositories import IKanbanRepository, InMemoryKanbanRepository
from .services import (
    BoardAdminService,
    CardWorkflowService,
    IAutomationRunner,
    ICardSearcher,
    InMemoryCardSearcher,
    SyncAutomationRunner,
    _KanbanServiceCore,
)

# ============= MAIN FACADE =============


class KanbanFacade:
    """The primary, public entry point for the Kanban core library."""

    def __init__(
        self,
        repository: IKanbanRepository,
        event_bus: EventBus,
        permission_checker: PermissionChecker | None = None,
        searcher: ICardSearcher | None = None,
        automation_runner: IAutomationRunner | None = None,
        clock: Clock | None = None,
        id_factory: IDFactory | None = None,
    ):
        # Setup default dependencies if not provided
        _clock = clock or (lambda: datetime.now(timezone.utc))
        _id_factory = id_factory or (lambda: str(uuid.uuid4()))
        _permission_checker = permission_checker or SimplePermissionChecker()
        _searcher = searcher or InMemoryCardSearcher()
        _automation_runner = automation_runner or SyncAutomationRunner()

        # The core context holds all shared state and logic
        self.core = _KanbanServiceCore(
            repository=repository,
            event_bus=event_bus,
            permission_checker=_permission_checker,
            searcher=_searcher,
            automation_runner=_automation_runner,
            clock=_clock,
            id_factory=_id_factory,
        )

        # Compose the specific services, providing them with the core context
        self.admin = BoardAdminService(self.core)
        self.cards = CardWorkflowService(self.core)

    def get_board(self, board_id: str, user_id: str) -> Board | None:
        """Retrieves a board if the user has VIEW_BOARD permission."""
        try:
            return self.core.get_board_and_check_permission(
                board_id, user_id, Permission.VIEW_BOARD
            )
        except (NotFoundError, PermissionError):
            return None

    def search_cards(self, board_id: str, user_id: str, **filters) -> list[Card]:
        """Searches for cards on a board."""
        board = self.get_board(board_id, user_id)
        if not board:
            return []
        return self.core.searcher.search(board, **filters)

    def execute(self, command: object) -> object | None:
        match command:
            case CreateBoard():
                return self.admin.create_board(
                    command.name, command.owner_id, command.columns
                )
            case UpdateBoard():
                return self.admin.update_board(
                    command.board_id, command.user_id, **command.kwargs
                )
            case DeleteBoard():
                return self.admin.delete_board(command.board_id, command.user_id)
            case CreateColumn():
                return self.admin.create_column(
                    command.board_id, command.user_id, command.name, command.position
                )
            case UpdateColumn():
                return self.admin.update_column(
                    command.board_id,
                    command.column_id,
                    command.user_id,
                    **command.kwargs,
                )
            case DeleteColumn():
                return self.admin.delete_column(
                    command.board_id, command.column_id, command.user_id
                )
            case AddCard():
                return self.cards.create_card(
                    command.board_id,
                    command.column_id,
                    command.title,
                    command.user_id,
                    **command.kwargs,
                )
            case UpdateCard():
                return self.cards.update_card(
                    command.board_id, command.card_id, command.user_id, **command.kwargs
                )
            case DeleteCard():
                return self.cards.delete_card(
                    command.board_id, command.card_id, command.user_id
                )
            case MoveCard():
                return self.cards.move_card(
                    command.board_id,
                    command.card_id,
                    command.to_column_id,
                    command.position,
                    command.user_id,
                )
            case BlockCard():
                return self.cards.block_card_dependency(
                    command.board_id,
                    command.blocking_card_id,
                    command.card_to_block_id,
                    command.user_id,
                )
            case UnblockCard():
                return self.cards.unblock_card_dependency(
                    command.board_id,
                    command.blocking_card_id,
                    command.card_to_unblock_id,
                    command.user_id,
                )
            case _:
                raise NotImplementedError(type(command).__name__)


# ============= SIMPLE FACADE =============


class SimpleKanban:
    """Simple facade for basic kanban usage, now using the decomposed KanbanFacade."""

    def __init__(self, id_factory: IDFactory | None = None):
        self.repository = InMemoryKanbanRepository()
        self.event_bus = EventBus()
        # The main facade is the single entry point.
        self.facade = KanbanFacade(
            self.repository, self.event_bus, id_factory=id_factory
        )
        self._default_user = "default_user"

    def create_board(
        self, user_id: str, name: str, columns: list[str] | None = None
    ) -> Board:
        return self.facade.execute(
            CreateBoard(name=name, owner_id=user_id, columns=columns)
        )

    def add_card(
        self, user_id: str, board_id: str, column_name: str, title: str, **kwargs
    ) -> Card:
        board = self.facade.get_board(board_id, user_id)
        if not board:
            raise ValueError("Board not found")
        column = next(
            (c for c in board.columns.values() if c.name == column_name), None
        )
        if not column:
            raise ValueError(f"Column '{column_name}' not found")
        # Delegate to the card service
        return self.facade.cards.create_card(
            board_id, column.id, title, user_id, **kwargs
        )

    def block_card(
        self, user_id: str, board_id: str, card_to_block_id: str, blocking_card_id: str
    ):
        # Delegate to the card service
        self.facade.cards.block_card_dependency(
            board_id, blocking_card_id, card_to_block_id, user_id
        )

    # ------------------------------------------------------------------
    # NEW CONVENIENCE METHODS
    # ------------------------------------------------------------------

    # ---- board helpers ------------------------------------------------
    def get_board(self, board_id: str, user_id: str | None = None) -> Board | None:
        return self.facade.get_board(board_id, user_id or self._default_user)

    def update_board(self, user_id: str, board_id: str, **changes) -> Board:
        return self.facade.execute(
            UpdateBoard(board_id=board_id, user_id=user_id, kwargs=changes)
        )

    def delete_board(self, user_id: str, board_id: str) -> None:
        self.facade.execute(DeleteBoard(board_id=board_id, user_id=user_id))

    def list_boards(self, user_id: str | None = None) -> list[Board]:
        uid = user_id or self._default_user
        return [
            b
            for b in self.repository.list_all()
            if self.facade.core.permission_checker.has_permission(
                uid, b, Permission.VIEW_BOARD
            )
        ]

    # ---- column helpers ----------------------------------------------
    def add_column(
        self, user_id: str, board_id: str, name: str, position: int | None = None
    ) -> Column:
        return self.facade.execute(
            CreateColumn(
                board_id=board_id, user_id=user_id, name=name, position=position
            )
        )

    def update_column(
        self, user_id: str, board_id: str, column_id: str, **changes
    ) -> Column:
        return self.facade.execute(
            UpdateColumn(
                board_id=board_id, column_id=column_id, user_id=user_id, kwargs=changes
            )
        )

    def delete_column(self, user_id: str, board_id: str, column_id: str) -> None:
        self.facade.execute(
            DeleteColumn(board_id=board_id, column_id=column_id, user_id=user_id)
        )

    # ---- card helpers -------------------------------------------------
    def update_card(self, user_id: str, board_id: str, card_id: str, **changes) -> Card:
        return self.facade.execute(
            UpdateCard(
                board_id=board_id, card_id=card_id, user_id=user_id, kwargs=changes
            )
        )

    def move_card(
        self,
        user_id: str,
        board_id: str,
        card_id: str,
        to_column_name: str,
        position: int | None = None,
    ) -> Card:
        board = self.facade.get_board(board_id, user_id)
        if not board:
            raise ValueError("Board not found")
        to_col = next(
            (c for c in board.columns.values() if c.name == to_column_name), None
        )
        if not to_col:
            raise ValueError(f"Column '{to_column_name}' not found")
        return self.facade.execute(
            MoveCard(
                board_id=board_id,
                card_id=card_id,
                to_column_id=to_col.id,
                position=position,
                user_id=user_id,
            )
        )

    def delete_card(self, user_id: str, board_id: str, card_id: str) -> None:
        self.facade.execute(
            DeleteCard(board_id=board_id, card_id=card_id, user_id=user_id)
        )

    def unblock_card(
        self,
        user_id: str,
        board_id: str,
        card_to_unblock_id: str,
        blocking_card_id: str,
    ):
        self.facade.cards.unblock_card_dependency(
            board_id, blocking_card_id, card_to_unblock_id, user_id
        )

    # ---- misc helpers -------------------------------------------------
    def search_cards(self, user_id: str, board_id: str, **filters) -> list[Card]:
        return self.facade.search_cards(board_id, user_id, **filters)

    def get_events(self, since: datetime | None = None) -> list[Event]:
        return self.event_bus.get_events(since)
