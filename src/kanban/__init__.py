"""
Kanban Core Library - A comprehensive, extensible kanban board implementation

This module provides a standard-library-only default implementation designed with
dependency injection in mind, allowing you to easily plug in external libraries
for persistence, search, automation, or other advanced features.
"""

# Main public API imports
from .automation import create_auto_move_rule, create_due_date_warning_rule
from .commands import (
    AddCard,
    BlockCard,
    CreateBoard,
    CreateColumn,
    DeleteBoard,
    DeleteCard,
    DeleteColumn,
    MoveCard,
    UnblockCard,
    UpdateBoard,
    UpdateCard,
    UpdateColumn,
)

# Event constants for convenience
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
    CORE_EVENTS,
    Event,
    EventBus,
    EventRegistry,
)
from .exceptions import (
    Clock,
    ConcurrencyError,
    IDFactory,
    KanbanError,
    NotFoundError,
    PermissionError,
    ValidationError,
    Validator,
    utc_clock,
    uuid4_factory,
)
from .facade import KanbanFacade, SimpleKanban
from .metrics import ICalendar, MetricsCalculator, TwentyFourSevenCalendar
from .models import (
    AutomationRule,
    Board,
    Card,
    Column,
    ColumnPolicy,
    CustomField,
    FieldType,
    Swimlane,
)
from .permissions import Permission, PermissionChecker, SimplePermissionChecker
from .repositories import IKanbanRepository, InMemoryKanbanRepository
from .services import (
    BoardAdminService,
    CardWorkflowService,
    EventFactory,
    IAutomationRunner,
    ICardSearcher,
    InMemoryCardSearcher,
    SyncAutomationRunner,
    _KanbanServiceCore,
)

__version__ = "1.0.0"

__all__ = [
    # Main facades
    "KanbanFacade",
    "SimpleKanban",
    # Core models
    "Board",
    "Card",
    "Column",
    "CustomField",
    "FieldType",
    "Swimlane",
    "AutomationRule",
    "ColumnPolicy",
    # Events
    "Event",
    "EventBus",
    "EventRegistry",
    "CORE_EVENTS",
    "CARD_MOVED",
    "CARD_UPDATED",
    "CARD_CREATED",
    "CARD_DELETED",
    "COLUMN_UPDATED",
    "COLUMN_CREATED",
    "COLUMN_DELETED",
    "BOARD_CREATED",
    "BOARD_UPDATED",
    "BOARD_DELETED",
    "CARD_BLOCKED",
    "CARD_UNBLOCKED",
    # Repositories
    "IKanbanRepository",
    "InMemoryKanbanRepository",
    # Permissions
    "Permission",
    "PermissionChecker",
    "SimplePermissionChecker",
    # Services
    "ICardSearcher",
    "InMemoryCardSearcher",
    "IAutomationRunner",
    "SyncAutomationRunner",
    "BoardAdminService",
    "CardWorkflowService",
    "EventFactory",
    "_KanbanServiceCore",
    # Metrics
    "MetricsCalculator",
    "ICalendar",
    "TwentyFourSevenCalendar",
    # Exceptions and types
    "KanbanError",
    "ValidationError",
    "PermissionError",
    "NotFoundError",
    "ConcurrencyError",
    "Clock",
    "IDFactory",
    "utc_clock",
    "uuid4_factory",
    "Validator",
    # Commands
    "CreateBoard",
    "UpdateBoard",
    "DeleteBoard",
    "CreateColumn",
    "UpdateColumn",
    "DeleteColumn",
    "AddCard",
    "UpdateCard",
    "DeleteCard",
    "MoveCard",
    "BlockCard",
    "UnblockCard",
    # Automation
    "create_auto_move_rule",
    "create_due_date_warning_rule",
]
