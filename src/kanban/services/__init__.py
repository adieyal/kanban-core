"""Service layer components for the kanban library."""

from .automation import AutomationContext, IAutomationRunner, SyncAutomationRunner
from .board_admin import BoardAdminService
from .card_workflow import CardWorkflowService
from .core import EventFactory, _KanbanServiceCore
from .search import ICardSearcher, InMemoryCardSearcher

__all__ = [
    # Search
    "ICardSearcher",
    "InMemoryCardSearcher",
    # Automation
    "IAutomationRunner",
    "AutomationContext",
    "SyncAutomationRunner",
    # Core
    "EventFactory",
    "_KanbanServiceCore",
    # Services
    "CardWorkflowService",
    "BoardAdminService",
]