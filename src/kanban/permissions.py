from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Protocol


class Permission(Enum):
    VIEW_BOARD = auto()
    EDIT_BOARD = auto()
    DELETE_BOARD = auto()
    CREATE_CARD = auto()
    EDIT_CARD = auto()
    MOVE_CARD = auto()
    DELETE_CARD = auto()
    CREATE_COLUMN = auto()
    EDIT_COLUMN = auto()
    DELETE_COLUMN = auto()
    MANAGE_USERS = auto()
    MANAGE_AUTOMATION = auto()


@dataclass(frozen=True, slots=True)
class PermissionContext:
    board_id: str
    owner_id: str
    team_ids: frozenset[str]


class PermissionPolicy(Protocol):
    def has_permission(
        self, user_id: str, context: PermissionContext, permission: Permission
    ) -> bool: ...


class SimplePermissionPolicy:
    DEFAULT_MEMBER_PERMISSIONS = {
        Permission.VIEW_BOARD,
        Permission.CREATE_CARD,
        Permission.EDIT_CARD,
        Permission.MOVE_CARD,
        Permission.DELETE_CARD,
        Permission.CREATE_COLUMN,
        Permission.EDIT_COLUMN,
        Permission.DELETE_COLUMN,
    }

    def __init__(self, member_permissions: set[Permission] | None = None):
        self.member_permissions = (
            set(member_permissions)
            if member_permissions is not None
            else set(self.DEFAULT_MEMBER_PERMISSIONS)
        )

    def has_permission(
        self, user_id: str, context: PermissionContext, permission: Permission
    ) -> bool:
        if not user_id:
            return False
        if context.owner_id == user_id:
            return True
        if user_id in context.team_ids:
            return permission in self.member_permissions
        return False
