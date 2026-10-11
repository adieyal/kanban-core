"""Public historical-state inputs; external store translation belongs to the host."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .attributes import copy_attributes, freeze_attributes
from .exceptions import ValidationError
from .models import WipGroup


def _text_fields(**values: object) -> None:
    for name, value in values.items():
        if not isinstance(value, str):
            raise ValidationError(f"Import {name} must be a string")


def _optional_timestamps(**values: object) -> None:
    for name, value in values.items():
        if value is not None and not isinstance(value, datetime):
            raise ValidationError(f"Import {name} must be a datetime or None")


@dataclass(frozen=True, slots=True)
class CardImport:
    id: str
    column_id: str
    title: str
    description: str = ""
    attributes: Mapping[str, object] = field(default_factory=dict)
    blocked_by: frozenset[str] = frozenset()
    assignee_ids: frozenset[str] = frozenset()
    due_date: datetime | None = None
    size: float | None = None
    archived: bool = False
    created_at: datetime | None = None
    entered_column_at: datetime | None = None
    blocked_reason: str | None = None
    blocked_at: datetime | None = None

    def __post_init__(self) -> None:
        _text_fields(
            id=self.id,
            column_id=self.column_id,
            title=self.title,
            description=self.description,
        )
        _optional_timestamps(
            due_date=self.due_date,
            created_at=self.created_at,
            entered_column_at=self.entered_column_at,
            blocked_at=self.blocked_at,
        )
        if self.blocked_reason is not None:
            _text_fields(blocked_reason=self.blocked_reason)
        if type(self.archived) is not bool:
            raise ValidationError("Import archived must be a bool")
        if self.size is not None and (
            type(self.size) not in (int, float) or not math.isfinite(self.size)
        ):
            raise ValidationError("Import size must be a finite number or None")
        object.__setattr__(
            self, "attributes", freeze_attributes(copy_attributes(self.attributes))
        )
        object.__setattr__(self, "blocked_by", frozenset(self.blocked_by))
        object.__setattr__(self, "assignee_ids", frozenset(self.assignee_ids))
        for identifier in self.blocked_by | self.assignee_ids:
            _text_fields(reference_id=identifier)


@dataclass(frozen=True, slots=True)
class ColumnImport:
    id: str
    name: str
    wip_limit: int | None = None
    max_age: timedelta | None = None
    color: str | None = None

    def __post_init__(self) -> None:
        _text_fields(id=self.id, name=self.name)
        if self.color is not None:
            _text_fields(color=self.color)
        if self.max_age is not None and not isinstance(self.max_age, timedelta):
            raise ValidationError("Import max_age must be a timedelta or None")
        if self.wip_limit is not None and type(self.wip_limit) is not int:
            raise ValidationError("Import wip_limit must be an integer or None")


@dataclass(frozen=True, slots=True)
class BoardImport:
    id: str
    name: str
    owner_id: str
    columns: tuple[ColumnImport, ...]
    cards: tuple[CardImport, ...] = ()
    description: str = ""
    team_ids: frozenset[str] = frozenset()
    created_at: datetime | None = None
    updated_at: datetime | None = None
    wip_groups: tuple[WipGroup, ...] = ()

    def __post_init__(self) -> None:
        _text_fields(
            id=self.id,
            name=self.name,
            owner_id=self.owner_id,
            description=self.description,
        )
        _optional_timestamps(created_at=self.created_at, updated_at=self.updated_at)
        object.__setattr__(self, "columns", tuple(self.columns))
        object.__setattr__(self, "cards", tuple(self.cards))
        object.__setattr__(self, "team_ids", frozenset(self.team_ids))
        object.__setattr__(self, "wip_groups", tuple(self.wip_groups))
        if any(not isinstance(item, ColumnImport) for item in self.columns):
            raise ValidationError("Import columns must be ColumnImport values")
        if any(not isinstance(item, CardImport) for item in self.cards):
            raise ValidationError("Import cards must be CardImport values")
        if any(not isinstance(item, WipGroup) for item in self.wip_groups):
            raise ValidationError("Import groups must be WipGroup values")
        for identifier in self.team_ids:
            _text_fields(team_id=identifier)
