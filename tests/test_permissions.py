"""Tests for permission system."""

from kanban.models import Board
from kanban.permissions import Permission, SimplePermissionPolicy


class TestSimplePermissionPolicy:
    """Test simple permission checker implementation."""

    def test_owner_has_all_permissions(self):
        """Test that board owners have all permissions."""
        checker = SimplePermissionPolicy()
        board = Board(id="board1", owner_id="owner1")

        # Owner should have all permissions
        for permission in Permission:
            assert checker.has_permission("owner1", board, permission)

    def test_team_member_default_permissions(self):
        """Test team member default permissions."""
        checker = SimplePermissionPolicy()
        board = Board(id="board1", owner_id="owner1", team_ids={"member1"})

        # Team member should have default permissions
        default_perms = SimplePermissionPolicy.DEFAULT_MEMBER_PERMISSIONS
        for permission in Permission:
            expected = permission in default_perms
            actual = checker.has_permission("member1", board, permission)
            assert actual == expected, f"Permission {permission} mismatch"

    def test_custom_member_permissions(self):
        """Test custom member permissions."""
        custom_perms = {Permission.VIEW_BOARD, Permission.CREATE_CARD}
        checker = SimplePermissionPolicy(member_permissions=custom_perms)
        board = Board(id="board1", owner_id="owner1", team_ids={"member1"})

        # Should only have custom permissions
        assert checker.has_permission("member1", board, Permission.VIEW_BOARD)
        assert checker.has_permission("member1", board, Permission.CREATE_CARD)
        assert not checker.has_permission("member1", board, Permission.DELETE_BOARD)

    def test_non_member_no_permissions(self):
        """Test that non-members have no permissions."""
        checker = SimplePermissionPolicy()
        board = Board(id="board1", owner_id="owner1", team_ids={"member1"})

        # Non-member should have no permissions
        for permission in Permission:
            assert not checker.has_permission("outsider", board, permission)

    def test_empty_user_id(self):
        """Test permission check with empty user ID."""
        checker = SimplePermissionPolicy()
        board = Board(id="board1", owner_id="owner1")

        assert not checker.has_permission("", board, Permission.VIEW_BOARD)
        assert not checker.has_permission(None, board, Permission.VIEW_BOARD)

    def test_empty_board(self):
        """Test permission check with empty board."""
        checker = SimplePermissionPolicy()

        assert not checker.has_permission("user1", None, Permission.VIEW_BOARD)
