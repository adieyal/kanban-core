from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum, auto

from .models import Board

# ============= PERMISSIONS =============


class Permission(Enum):
    """Granular permissions"""

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


class PermissionChecker(ABC):
    @abstractmethod
    def has_permission(
        self, user_id: str, board: Board, permission: Permission
    ) -> bool:
        pass


class SimplePermissionChecker(PermissionChecker):
    """
    Basic checker. Owners have all rights. Team members have a configurable set of rights.
    """

    DEFAULT_MEMBER_PERMISSIONS = {
        Permission.VIEW_BOARD,
        Permission.CREATE_CARD,
        Permission.EDIT_CARD,
        Permission.MOVE_CARD,
        Permission.DELETE_CARD,
        Permission.CREATE_COLUMN,
        Permission.EDIT_COLUMN,
        ## FIX 4.1.1: Add destructive column permissions to the default set for completeness.
        Permission.DELETE_COLUMN,
    }

    ## FIX 4.1.2: The set of member permissions is now configurable.
    def __init__(self, member_permissions: set[Permission] | None = None):
        self.member_permissions = member_permissions or self.DEFAULT_MEMBER_PERMISSIONS

    def has_permission(
        self, user_id: str, board: Board, permission: Permission
    ) -> bool:
        if not board or not user_id:
            return False
        if board.owner_id == user_id:
            return True
        if user_id in board.team_ids:
            return permission in self.member_permissions
        return False
