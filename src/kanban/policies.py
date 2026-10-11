"""Public, read-only extension points for organization-specific workflow rules."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol

from .attributes import freeze_attributes


@dataclass(frozen=True, slots=True)
class ColumnPolicyContext:
    """Column observations from the board participating in this operation."""

    id: str
    name: str
    card_count: int
    wip_limit: int | None
    max_age: timedelta | None


@dataclass(frozen=True, slots=True)
class CardPolicyContext:
    """A detached card snapshot supplied to an external workflow policy."""

    board_id: str
    user_id: str
    card_id: str
    column_id: str
    title: str
    description: str
    assignee_ids: frozenset[str]
    due_date: datetime | None
    size: float | None
    archived: bool
    blocked_reason: str | None = None
    blocked_at: datetime | None = None
    is_blocked: bool = False

    attributes: Mapping[str, object] = field(default_factory=dict)
    columns: tuple[ColumnPolicyContext, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "attributes", freeze_attributes(self.attributes))
        object.__setattr__(self, "columns", tuple(self.columns))

    def column(self, column_id: str) -> ColumnPolicyContext | None:
        return next((column for column in self.columns if column.id == column_id), None)


@dataclass(frozen=True, slots=True)
class CardMovePolicyContext:
    """The proposed card transition, before the aggregate is mutated."""

    card: CardPolicyContext
    from_column_id: str
    to_column_id: str
    position: int

    @property
    def columns(self) -> tuple[ColumnPolicyContext, ...]:
        return self.card.columns

    @property
    def from_column(self) -> ColumnPolicyContext | None:
        return self.card.column(self.from_column_id)

    @property
    def to_column(self) -> ColumnPolicyContext | None:
        return self.card.column(self.to_column_id)


class WorkflowPolicy(Protocol):
    """Optional policy port for deployment-specific card lifecycle rules.

    Implementations validate only. They must not persist data, publish events, or
    mutate the supplied contexts. A rejected operation should raise
    ``kanban.ValidationError`` (or a subclass).
    """

    def validate_create(self, context: CardPolicyContext) -> None: ...

    def validate_update(self, context: CardPolicyContext) -> None: ...

    def validate_move(self, context: CardMovePolicyContext) -> None: ...

    def validate_delete(self, context: CardPolicyContext) -> None: ...


class AllowAllWorkflowPolicy:
    """Default policy; structural domain invariants still apply."""

    def validate_create(self, context: CardPolicyContext) -> None:
        pass

    def validate_update(self, context: CardPolicyContext) -> None:
        pass

    def validate_move(self, context: CardMovePolicyContext) -> None:
        pass

    def validate_delete(self, context: CardPolicyContext) -> None:
        pass
