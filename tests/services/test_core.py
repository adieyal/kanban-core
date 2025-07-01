"""Tests for core service infrastructure."""

import copy
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from kanban import (
    Board,
    Card,
    Column,
    ColumnPolicy,
    Event,
    EventBus,
    EventFactory,
    IKanbanRepository,
    InMemoryCardSearcher,
    NotFoundError,
    Permission,
    PermissionChecker,
    PermissionError,
    SyncAutomationRunner,
    ValidationError,
    _KanbanServiceCore,
)
from kanban.services import AutomationContext


class TestEventFactory:
    """Test event creation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.clock = Mock(return_value=datetime.now(timezone.utc))
        self.id_factory = Mock(return_value="event123")
        self.factory = EventFactory(self.clock, self.id_factory)

    def test_create_event_with_all_fields(self):
        """Test creating event with all fields."""
        event = self.factory.create(
            event_type="card.created",
            entity_id="card1",
            entity_type="card",
            user_id="user1",
            data={"key": "value"}
        )
        
        assert event.type == "card.created"
        assert event.entity_id == "card1"
        assert event.entity_type == "card"
        assert event.user_id == "user1"
        assert event.data == {"key": "value"}
        assert event.id == "event123"
        assert event.timestamp == self.clock.return_value
        
        self.clock.assert_called_once()
        self.id_factory.assert_called_once()

    def test_create_event_with_none_user_id(self):
        """Test creating event with None user_id."""
        event = self.factory.create(
            event_type="card.moved",
            entity_id="card1",
            entity_type="card",
            user_id=None,
            data={}
        )
        
        assert event.user_id is None


class TestKanbanServiceCore:
    """Test core service functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.repository = Mock(spec=IKanbanRepository)
        self.event_bus = Mock(spec=EventBus)
        self.permission_checker = Mock(spec=PermissionChecker)
        self.searcher = Mock(spec=InMemoryCardSearcher)
        self.automation_runner = Mock(spec=SyncAutomationRunner)
        self.clock = Mock(return_value=datetime.now(timezone.utc))
        self.id_factory = Mock(return_value="id123")
        
        self.core = _KanbanServiceCore(
            repository=self.repository,
            event_bus=self.event_bus,
            permission_checker=self.permission_checker,
            searcher=self.searcher,
            automation_runner=self.automation_runner,
            clock=self.clock,
            id_factory=self.id_factory,
        )
        
        self.board = Board(
            id="board1",
            name="Test Board",
            owner_id="user1",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            version=1,
        )

    def test_get_board_and_check_permission_success(self):
        """Test successful board retrieval with permission."""
        self.repository.get.return_value = self.board
        self.permission_checker.has_permission.return_value = True
        
        result = self.core.get_board_and_check_permission(
            "board1", "user1", Permission.VIEW_BOARD
        )
        
        assert result == self.board
        self.repository.get.assert_called_once_with("board1")
        self.permission_checker.has_permission.assert_called_once_with(
            "user1", self.board, Permission.VIEW_BOARD
        )

    def test_get_board_and_check_permission_board_not_found(self):
        """Test board not found raises NotFoundError."""
        self.repository.get.return_value = None
        
        with pytest.raises(NotFoundError, match="Board 'board1' not found"):
            self.core.get_board_and_check_permission(
                "board1", "user1", Permission.VIEW_BOARD
            )

    def test_get_board_and_check_permission_no_permission(self):
        """Test permission denied raises PermissionError."""
        self.repository.get.return_value = self.board
        self.permission_checker.has_permission.return_value = False
        
        with pytest.raises(PermissionError, match="User 'user1' lacks permission"):
            self.core.get_board_and_check_permission(
                "board1", "user1", Permission.DELETE_BOARD
            )

    def test_execute_transaction_no_changes_no_save(self):
        """Test transaction with no changes doesn't save."""
        self.repository.get.return_value = self.board
        self.permission_checker.has_permission.return_value = True
        self.automation_runner.run.return_value = False
        
        def action(board, ctx):
            return "result", []
        
        result, final_board = self.core._execute_transaction(
            "board1", "user1", Permission.VIEW_BOARD, action
        )
        
        assert result == "result"
        assert final_board == self.board
        self.repository.save.assert_not_called()

    def test_execute_transaction_with_action_changes_saves(self):
        """Test transaction with action changes saves board."""
        self.repository.get.return_value = self.board
        self.permission_checker.has_permission.return_value = True
        self.automation_runner.run.return_value = False
        saved_board = copy.deepcopy(self.board)
        saved_board.version = 2
        self.repository.save.return_value = saved_board
        
        def action(board, ctx):
            board.name = "Modified Board"  # This modifies the board
            event = Event(
                type="test.event",
                entity_id="board1",
                entity_type="board",
                id="event1",
                timestamp=self.clock(),
            )
            return "result", [event]
        
        result, final_board = self.core._execute_transaction(
            "board1", "user1", Permission.EDIT_BOARD, action
        )
        
        assert result == "result"
        assert final_board.version == 2
        self.repository.save.assert_called_once_with(self.board, expected_version=1)
        self.event_bus.publish.assert_called_once()

    def test_execute_transaction_with_automation_changes_saves(self):
        """Test transaction with automation changes saves board."""
        self.repository.get.return_value = self.board
        self.permission_checker.has_permission.return_value = True
        self.automation_runner.run.return_value = True  # Automation made changes
        saved_board = copy.deepcopy(self.board)
        saved_board.version = 2
        self.repository.save.return_value = saved_board
        
        def action(board, ctx):
            event = Event(
                type="test.event",
                entity_id="board1",
                entity_type="board",
                id="event1",
                timestamp=self.clock(),
            )
            return "result", [event]
        
        result, final_board = self.core._execute_transaction(
            "board1", "user1", Permission.VIEW_BOARD, action
        )
        
        assert result == "result"
        assert final_board.version == 2
        self.repository.save.assert_called_once()

    def test_internal_move_successful(self):
        """Test successful card move between columns."""
        # Setup board with columns and card
        col1 = Column(id="col1", board_id="board1", name="Col1", position=0)
        col1.card_ids = ["card1"]
        col2 = Column(id="col2", board_id="board1", name="Col2", position=1)
        col2.policy = ColumnPolicy()  # Allow card entry
        
        card = Card(id="card1", column_id="col1", title="Test Card")
        
        self.board.columns = {"col1": col1, "col2": col2}
        self.board.cards = {"card1": card}
        
        result = self.core._internal_move(self.board, "card1", "col2")
        
        assert result == card
        assert card.column_id == "col2"
        assert "card1" not in col1.card_ids
        assert "card1" in col2.card_ids
        self.event_bus.publish.assert_called_once()

    def test_internal_move_validation_error(self):
        """Test card move fails validation."""
        col1 = Column(id="col1", board_id="board1", name="Col1", position=0)
        col1.card_ids = ["card1"]
        col2 = Column(id="col2", board_id="board1", name="Col2", position=1)
        col2.policy = ColumnPolicy(wip_limit=0)  # Doesn't allow any cards
        
        card = Card(id="card1", column_id="col1", title="Test Card")
        
        self.board.columns = {"col1": col1, "col2": col2}
        self.board.cards = {"card1": card}
        
        with pytest.raises(ValidationError):
            self.core._internal_move(self.board, "card1", "col2")