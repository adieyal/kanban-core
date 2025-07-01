from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ============= COMMAND CLASSES =============


@dataclass(frozen=True, slots=True)
class CreateBoard:
    name: str
    owner_id: str
    columns: list[str] | None = None


@dataclass(frozen=True, slots=True)
class UpdateBoard:
    board_id: str
    user_id: str
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DeleteBoard:
    board_id: str
    user_id: str


@dataclass(frozen=True, slots=True)
class CreateColumn:
    board_id: str
    user_id: str
    name: str
    position: int | None = None


@dataclass(frozen=True, slots=True)
class UpdateColumn:
    board_id: str
    column_id: str
    user_id: str
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DeleteColumn:
    board_id: str
    column_id: str
    user_id: str


@dataclass(frozen=True, slots=True)
class AddCard:
    board_id: str
    column_id: str
    title: str
    user_id: str
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class UpdateCard:
    board_id: str
    card_id: str
    user_id: str
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DeleteCard:
    board_id: str
    card_id: str
    user_id: str


@dataclass(frozen=True, slots=True)
class MoveCard:
    board_id: str
    card_id: str
    to_column_id: str
    position: int | None
    user_id: str


@dataclass(frozen=True, slots=True)
class BlockCard:
    board_id: str
    blocking_card_id: str
    card_to_block_id: str
    user_id: str


@dataclass(frozen=True, slots=True)
class UnblockCard:
    board_id: str
    blocking_card_id: str
    card_to_unblock_id: str
    user_id: str
