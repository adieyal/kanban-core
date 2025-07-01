from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Protocol

from .exceptions import ValidationError

# ============= CORE DOMAIN MODELS =============


class FieldType(Enum):
    """Supported field types for custom fields"""

    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    SELECT = "select"
    MULTISELECT = "multiselect"
    USER = "user"


# ============= FIELD VALIDATOR REGISTRY =============


class FieldValidator(Protocol):
    def __call__(self, value: Any) -> None: ...


_VALIDATORS: dict[str, FieldValidator] = {}


def register_validator(name: str):
    def decorator(fn: FieldValidator):
        _VALIDATORS[name] = fn
        return fn

    return decorator


@dataclass
class CustomField:
    """
    Custom field definition.
    Now uses validator_ids and the global registry.
    """

    name: str
    field_type: FieldType
    required: bool = False
    options: list[str] | None = None  # For select/multiselect
    default_value: Any = None
    validator_ids: list[str] = field(default_factory=list)

    def validate(self, value: Any):
        for vid in self.validator_ids:
            try:
                _VALIDATORS[vid](value)
            except KeyError:
                raise ValidationError(
                    f"Unknown validator '{vid}' for field '{self.name}'"
                )


@dataclass
class Card:
    """Core card/item entity"""

    id: str
    column_id: str
    time_in_column: dict[str, timedelta] = field(default_factory=dict)
    title: str = ""
    description: str = ""
    position: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Relationships
    blocked_by: set[str] = field(default_factory=set)  # Card IDs that block this card
    blocks: set[str] = field(default_factory=set)  # Cards this card blocks
    parent_id: str | None = None
    child_ids: set[str] = field(default_factory=set)
    related_ids: set[str] = field(default_factory=set)

    # Metadata
    assignee_ids: set[str] = field(default_factory=set)
    due_date: datetime | None = None

    # Custom fields
    custom_fields: dict[str, Any] = field(default_factory=dict)

    # Time tracking
    entered_column_at: datetime | None = None

    # Advanced features
    size: float | None = None  # Story points, hours, etc.
    swimlane_id: str | None = None
    archived: bool = False
    version: int = 1

    def is_blocked(self) -> bool:
        return len(self.blocked_by) > 0

    def add_time_in_column(self, column_id: str, duration: timedelta):
        self.time_in_column[column_id] = (
            self.time_in_column.get(column_id, timedelta()) + duration
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert card to dictionary for serialization"""
        return {
            "id": self.id,
            "column_id": self.column_id,
            "title": self.title,
            "description": self.description,
            "position": self.position,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "blocked_by": sorted(list(self.blocked_by)),
            "blocks": sorted(list(self.blocks)),
            "parent_id": self.parent_id,
            "child_ids": sorted(list(self.child_ids)),
            "related_ids": sorted(list(self.related_ids)),
            "assignee_ids": sorted(list(self.assignee_ids)),
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "custom_fields": self.custom_fields,
            "entered_column_at": self.entered_column_at.isoformat()
            if self.entered_column_at
            else None,
            "size": self.size,
            "swimlane_id": self.swimlane_id,
            "archived": self.archived,
            "version": self.version,
        }


@dataclass
class ColumnPolicy:
    """
    Rules for column behavior.
    (REVISED: A-5) 'allowed_card_types' removed in favor of a generic 'entry_criteria' hook.
    """

    wip_limit: int | None = None
    auto_move_when_done: str | None = None  # Next column ID
    entry_criteria: Callable[[Card], bool] | None = None
    exit_criteria: Callable[[Card], bool] | None = None


@dataclass
class Column:
    """Board column/list"""

    id: str
    board_id: str
    name: str = ""
    position: int = 0
    policy: ColumnPolicy = field(default_factory=ColumnPolicy)
    card_ids: list[str] = field(default_factory=list)  # Ordered list
    color: str | None = None
    is_done_column: bool = False

    def can_accept_card(
        self, card: Card, is_new_entry: bool
    ) -> tuple[bool, str | None]:
        """
        Check if column can accept a card based on policies.
        'is_new_entry' is True if the card is coming from another column.
        """
        # FIX 2.2.1: Only check WIP limit if the card is a new entry into this column.
        if is_new_entry:
            if (
                self.policy.wip_limit is not None
                and len(self.card_ids) >= self.policy.wip_limit
            ):
                return False, f"WIP limit of {self.policy.wip_limit} would be exceeded."
            if self.policy.entry_criteria and not self.policy.entry_criteria(card):
                return False, "Card does not meet column entry criteria."
        return True, None


@dataclass
class Swimlane:
    """Horizontal grouping across columns"""

    id: str
    board_id: str
    name: str = ""
    position: int = 0
    color: str | None = None


@dataclass
class AutomationRule:
    """If-this-then-that automation"""

    id: str
    name: str = ""
    trigger: Callable = None
    action: Callable = None
    enabled: bool = True


@dataclass
class Board:
    """Kanban board entity"""

    id: str
    version: int = 1
    name: str = ""
    description: str = ""
    columns: dict[str, Column] = field(default_factory=dict)
    cards: dict[str, Card] = field(default_factory=dict)
    swimlanes: dict[str, Swimlane] = field(default_factory=dict)

    custom_fields: dict[str, CustomField] = field(default_factory=dict)
    automation_rules: list[AutomationRule] = field(default_factory=list)

    created_at: datetime | None = None
    updated_at: datetime | None = None
    owner_id: str | None = None
    team_ids: set[str] = field(default_factory=set)

    def get_columns_ordered(self) -> list[Column]:
        return sorted(self.columns.values(), key=lambda c: c.position)

    def get_cards_in_column(self, column_id: str) -> list[Card]:
        column = self.columns.get(column_id)
        if not column:
            return []
        return [
            self.cards[card_id] for card_id in column.card_ids if card_id in self.cards
        ]
