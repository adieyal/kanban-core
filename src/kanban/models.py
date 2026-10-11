from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from .attributes import copy_attributes
from .exceptions import ValidationError

# ============= CORE DOMAIN MODELS =============


@dataclass
class Card:
    """Core card/item entity."""

    id: str
    title: str = ""
    description: str = ""
    blocked_by: set[str] = field(default_factory=set)
    blocks: set[str] = field(default_factory=set)
    assignee_ids: set[str] = field(default_factory=set)
    due_date: datetime | None = None
    size: float | None = None
    archived: bool = False
    attributes: dict[str, object] = field(default_factory=dict)
    created_at: datetime | None = None
    entered_column_at: datetime | None = None

    def __post_init__(self) -> None:
        self.attributes = copy_attributes(self.attributes)

    blocked_reason: str | None = None
    blocked_at: datetime | None = None

    def is_blocked(self) -> bool:
        return bool(self.blocked_by) or self.blocked_reason is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "blocked_by": sorted(self.blocked_by),
            "blocks": sorted(self.blocks),
            "assignee_ids": sorted(self.assignee_ids),
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "size": self.size,
            "archived": self.archived,
            "attributes": copy_attributes(self.attributes),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "entered_column_at": (
                self.entered_column_at.isoformat() if self.entered_column_at else None
            ),
            "blocked_reason": self.blocked_reason,
            "blocked_at": self.blocked_at.isoformat() if self.blocked_at else None,
        }


@dataclass
class ColumnPolicy:
    """Rules for column behavior."""

    wip_limit: int | None = None
    max_age: timedelta | None = None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if self.max_age is not None and (
            not isinstance(self.max_age, timedelta) or self.max_age <= timedelta(0)
        ):
            raise ValidationError("Column max_age must be a positive timedelta")


@dataclass
class Column:
    """Board column/list."""

    id: str
    board_id: str
    name: str = ""
    position: int = 0
    policy: ColumnPolicy = field(default_factory=ColumnPolicy)
    card_ids: list[str] = field(default_factory=list)
    color: str | None = None

    def can_accept_card(self, is_new_entry: bool) -> tuple[bool, str | None]:
        if (
            is_new_entry
            and self.policy.wip_limit is not None
            and len(self.card_ids) >= self.policy.wip_limit
        ):
            return False, f"WIP limit of {self.policy.wip_limit} would be exceeded."
        return True, None


@dataclass
class Board:
    """Kanban board entity"""

    id: str
    version: int = 1
    name: str = ""
    description: str = ""
    columns: dict[str, Column] = field(default_factory=dict)
    cards: dict[str, Card] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    owner_id: str | None = None
    team_ids: set[str] = field(default_factory=set)

    def get_columns_ordered(self) -> list[Column]:
        return sorted(self.columns.values(), key=lambda c: c.position)

    def column_for_card(self, card_id: str) -> Column:
        for column in self.columns.values():
            if card_id in column.card_ids:
                return column
        raise ValidationError(f"Card '{card_id}' is not assigned to a column")

    def get_cards_in_column(self, column_id: str) -> list[Card]:
        column = self.columns.get(column_id)
        if not column:
            return []
        return [
            self.cards[card_id] for card_id in column.card_ids if card_id in self.cards
        ]
