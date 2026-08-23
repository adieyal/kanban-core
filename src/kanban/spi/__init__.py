"""Infrastructure and extension contracts for kanban integrations."""

from ..events import Event, EventPublisher
from ..exceptions import (
    Clock,
    ConcurrencyError,
    IDFactory,
    InvalidPersistenceStateError,
)
from ..permissions import PermissionContext, PermissionPolicy
from ..policies import CardMovePolicyContext, CardPolicyContext, WorkflowPolicy
from ..repositories import BoardSnapshot, KanbanRepository
from ..services import CardSearcher
from ..services.search import SearchCard, SearchContext
from ..unit_of_work import KanbanUnitOfWork
from .automation import (
    AutomationAction,
    AutomationCardFacts,
    AutomationColumnFacts,
    AutomationFacts,
    AutomationRunner,
    MoveCardAction,
)

__all__ = [
    "AutomationRunner",
    "AutomationAction",
    "AutomationCardFacts",
    "AutomationColumnFacts",
    "AutomationFacts",
    "BoardSnapshot",
    "CardMovePolicyContext",
    "CardPolicyContext",
    "CardSearcher",
    "Clock",
    "ConcurrencyError",
    "Event",
    "EventPublisher",
    "IDFactory",
    "InvalidPersistenceStateError",
    "KanbanRepository",
    "KanbanUnitOfWork",
    "PermissionContext",
    "PermissionPolicy",
    "MoveCardAction",
    "SearchCard",
    "SearchContext",
    "WorkflowPolicy",
]
