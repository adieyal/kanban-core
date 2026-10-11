from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from .attributes import attributes_equal, copy_attributes
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
    blocked_reason: str | None = None
    blocked_at: datetime | None = None

    def __post_init__(self) -> None:
        self.attributes = copy_attributes(self.attributes)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Card) or type(self) is not type(other):
            return NotImplemented
        return (
            self.id,
            self.title,
            self.description,
            self.blocked_by,
            self.blocks,
            self.assignee_ids,
            self.due_date,
            self.size,
            self.archived,
            self.created_at,
            self.entered_column_at,
            self.blocked_reason,
            self.blocked_at,
        ) == (
            other.id,
            other.title,
            other.description,
            other.blocked_by,
            other.blocks,
            other.assignee_ids,
            other.due_date,
            other.size,
            other.archived,
            other.created_at,
            other.entered_column_at,
            other.blocked_reason,
            other.blocked_at,
        ) and attributes_equal(self.attributes, other.attributes)

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


@dataclass(frozen=True, slots=True)
class WipGroup:
    """Capacity shared by a named set of columns."""

    name: str
    column_ids: tuple[str, ...]
    limit: int

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValidationError("WIP group name must not be empty")
        if type(self.limit) is not int or self.limit <= 0:
            raise ValidationError("WIP group limit must be a positive integer")
        if not isinstance(self.column_ids, (list, tuple)):
            raise ValidationError("WIP group columns must be a list or tuple")
        members = tuple(self.column_ids)
        if not members or any(
            not isinstance(item, str) or not item.strip() for item in members
        ):
            raise ValidationError("WIP group must contain nonempty column IDs")
        if len(set(members)) != len(members):
            raise ValidationError("WIP group column IDs must be distinct")
        object.__setattr__(self, "column_ids", members)


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
    wip_groups: tuple[WipGroup, ...] = ()

    def configure_wip_groups(self, groups: object) -> None:
        if not isinstance(groups, (list, tuple)) or any(
            not isinstance(group, WipGroup) for group in groups
        ):
            raise ValidationError(
                "WIP groups must be a list or tuple of WipGroup values"
            )
        if len({group.name for group in groups}) != len(groups):
            raise ValidationError("WIP group names must be distinct")
        if any(
            column_id not in self.columns
            for group in groups
            for column_id in group.column_ids
        ):
            raise ValidationError("WIP group references an unknown column")
        self.wip_groups = tuple(groups)

    def validate_group_entry(
        self, to_column_id: str, from_column_id: str | None = None
    ) -> None:
        for group in self.wip_groups:
            if (
                to_column_id not in group.column_ids
                or from_column_id in group.column_ids
            ):
                continue
            occupancy = sum(
                len(self.columns[column_id].card_ids) for column_id in group.column_ids
            )
            if occupancy >= group.limit:
                raise ValidationError(
                    f"WIP group '{group.name}' limit of {group.limit} would be exceeded"
                )

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
