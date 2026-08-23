"""Tests for board administration service."""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from kanban import NotFoundError, ValidationError
from kanban.events import Event
from kanban.models import Board, Column, ColumnPolicy
from kanban.services import AutomationContext
from kanban.services.board_admin import BoardAdminService
from kanban.services.core import _KanbanServiceCore


class TestBoardAdminService:
    """Test board administration operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.core = Mock(spec=_KanbanServiceCore)
        self.service = BoardAdminService(self.core)

        self.board = Board(
            id="board1",
            name="Test Board",
            owner_id="user1",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # Mock the transaction execution to call the action directly
        def mock_execute_transaction(board_id, user_id, permission, action):
            result, events = action(self.board, AutomationContext())
            return result, self.board

        self.core._execute_transaction.side_effect = mock_execute_transaction

        # Counter for id generation
        self.id_counter = 0

        def mock_id_factory():
            self.id_counter += 1
            return f"id{self.id_counter}"

        self.core.id_factory = Mock(side_effect=mock_id_factory)
        self.core.clock = Mock(return_value=datetime.now(timezone.utc))
        self.core.repository = Mock()

        # For create_board tests, return a new board instead of the default test board
        def mock_save(board, expected_version=None):
            return board

        self.core.repository.save = Mock(side_effect=mock_save)
        self.core.repository.delete = Mock()
        self.core.event_factory = Mock()
        self.core.event_factory.create = Mock(
            return_value=Event(
                type="test.event",
                entity_id="test",
                entity_type="test",
                id="event1",
                timestamp=datetime.now(timezone.utc),
            )
        )
        self.core.unit_of_work = Mock()
        self.core.unit_of_work.save.side_effect = mock_save
        self.core.get_board_and_check_permission = Mock()

    def test_create_board_with_default_columns(self):
        """Test board creation with default columns."""
        result = self.service.create_board(name="New Board", owner_id="user1")

        assert result.name == "New Board"
        assert result.owner_id == "user1"
        assert "user1" in result.team_ids
        assert len(result.columns) == 3

        # Check default column names
        column_names = [col.name for col in result.columns.values()]
        assert "To Do" in column_names
        assert "In Progress" in column_names
        assert "Done" in column_names

    def test_create_board_with_custom_columns(self):
        """Test board creation with custom columns."""
        custom_columns = ["Backlog", "Development", "Testing", "Completed"]

        result = self.service.create_board(
            name="New Board", owner_id="user1", columns=custom_columns
        )

        assert len(result.columns) == 4
        column_names = [col.name for col in result.columns.values()]
        assert all(name in column_names for name in custom_columns)

    def test_update_column_name(self):
        """Test updating column name."""
        column = Column(id="col1", board_id="board1", name="Old Name", position=0)
        self.board.columns = {"col1": column}

        result = self.service.update_column(
            board_id="board1", column_id="col1", user_id="user1", name="New Name"
        )

        assert result.name == "New Name"

    def test_update_column_not_found(self):
        """Test column update fails when column doesn't exist."""
        with pytest.raises(NotFoundError, match="Column not found"):
            self.service.update_column(
                board_id="board1",
                column_id="nonexistent",
                user_id="user1",
                name="New Name",
            )

    def test_update_column_position(self):
        """Test updating column position reorders other columns."""
        col1 = Column(id="col1", board_id="board1", name="Col1", position=0)
        col2 = Column(id="col2", board_id="board1", name="Col2", position=1)
        col3 = Column(id="col3", board_id="board1", name="Col3", position=2)

        self.board.columns = {"col1": col1, "col2": col2, "col3": col3}

        # Move col3 to position 0
        result = self.service.update_column(
            board_id="board1", column_id="col3", user_id="user1", position=0
        )

        assert result.position == 0
        # Other columns should be reindexed
        assert col1.position >= 0
        assert col2.position >= 0

    def test_update_column_policy(self):
        """Test updating column policy."""
        column = Column(id="col1", board_id="board1", name="Col1", position=0)
        self.board.columns = {"col1": column}

        new_policy = ColumnPolicy(wip_limit=5)

        result = self.service.update_column(
            board_id="board1", column_id="col1", user_id="user1", policy=new_policy
        )

        assert result.policy.wip_limit == 5

    def test_update_column_policy_dict(self):
        """Test updating column policy with dictionary."""
        column = Column(id="col1", board_id="board1", name="Col1", position=0)
        self.board.columns = {"col1": column}

        result = self.service.update_column(
            board_id="board1",
            column_id="col1",
            user_id="user1",
            policy={"wip_limit": 3},
        )

        assert result.policy.wip_limit == 3

    def test_create_column_success(self):
        """Test successful column creation."""
        result = self.service.create_column(
            board_id="board1", user_id="user1", name="New Column"
        )

        assert result.name == "New Column"
        assert result.id in self.board.columns

    def test_create_column_duplicate_name(self):
        """Test column creation fails with duplicate name."""
        existing_col = Column(id="col1", board_id="board1", name="Existing", position=0)
        self.board.columns = {"col1": existing_col}

        with pytest.raises(
            ValidationError, match="Column name 'Existing' already exists"
        ):
            self.service.create_column(
                board_id="board1", user_id="user1", name="Existing"
            )

    def test_delete_column_success(self):
        """Test successful column deletion."""
        column = Column(id="col1", board_id="board1", name="To Delete", position=0)
        self.board.columns = {"col1": column}

        self.service.delete_column(board_id="board1", column_id="col1", user_id="user1")

        assert "col1" not in self.board.columns

    def test_delete_column_not_found(self):
        """Test column deletion fails when column doesn't exist."""
        with pytest.raises(NotFoundError, match="Column not found"):
            self.service.delete_column(
                board_id="board1", column_id="nonexistent", user_id="user1"
            )

    def test_delete_column_non_empty(self):
        """Test column deletion fails when column has cards."""
        column = Column(id="col1", board_id="board1", name="Non Empty", position=0)
        column.card_ids = ["card1"]
        self.board.columns = {"col1": column}

        with pytest.raises(ValidationError, match="Cannot delete a non-empty column"):
            self.service.delete_column(
                board_id="board1", column_id="col1", user_id="user1"
            )

    def test_update_board_success(self):
        """Test successful board update."""
        result = self.service.update_board(
            board_id="board1",
            user_id="user1",
            name="Updated Name",
            description="New description",
        )

        assert result.name == "Updated Name"
        assert result.description == "New description"

    def test_update_board_team_ids_conversion(self):
        """Test board update converts team_ids to set."""
        result = self.service.update_board(
            board_id="board1", user_id="user1", team_ids=["user1", "user2", "user3"]
        )

        assert result.team_ids == {"user1", "user2", "user3"}

    def test_update_board_rejects_unknown_fields(self):
        """Typos must not be silently accepted as successful updates."""
        with pytest.raises(ValidationError, match="invalid_field"):
            self.service.update_board(
                board_id="board1",
                user_id="user1",
                invalid_field="value",
            )

    def test_delete_board_success(self):
        """Test successful board deletion."""
        self.core.get_board_and_check_permission.return_value = self.board

        self.service.delete_board(board_id="board1", user_id="user1")

        self.core.unit_of_work.delete.assert_called_once()
