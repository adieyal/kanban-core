"""Tests for card workflow service."""

import copy
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from kanban import (
    Board,
    Card,
    CardWorkflowService,
    Column,
    ColumnPolicy,
    Event,
    NotFoundError,
    Permission,
    ValidationError,
    _KanbanServiceCore,
)
from kanban.services import AutomationContext


class TestCardWorkflowService:
    """Test card workflow operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.core = Mock(spec=_KanbanServiceCore)
        self.service = CardWorkflowService(self.core)
        
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
        self.core.id_factory = Mock(return_value="card123")
        self.core.clock = Mock(return_value=datetime.now(timezone.utc))
        self.core.event_factory = Mock()
        self.core.event_factory.create = Mock(return_value=Event(
            type="test.event",
            entity_id="test",
            entity_type="test",
            id="event1",
            timestamp=datetime.now(timezone.utc)
        ))

    def test_create_card_success(self):
        """Test successful card creation."""
        col = Column(id="col1", board_id="board1", name="To Do", position=0)
        col.policy = ColumnPolicy()  # Allows card entry
        self.board.columns = {"col1": col}
        
        result = self.service.create_card(
            board_id="board1",
            column_id="col1",
            title="New Card",
            user_id="user1",
            description="Test description"
        )
        
        assert result.id == "card123"
        assert result.title == "New Card"
        assert result.description == "Test description"
        assert result.column_id == "col1"
        assert "card123" in self.board.cards
        assert "card123" in col.card_ids

    def test_create_card_column_not_found(self):
        """Test card creation fails when column doesn't exist."""
        with pytest.raises(NotFoundError, match="Column not found"):
            self.service.create_card(
                board_id="board1",
                column_id="nonexistent",
                title="New Card",
                user_id="user1"
            )

    def test_create_card_invalid_custom_fields(self):
        """Test card creation fails with invalid custom fields."""
        col = Column(id="col1", board_id="board1", name="To Do", position=0)
        self.board.columns = {"col1": col}
        
        with pytest.raises(ValidationError, match="Unknown custom field"):
            self.service.create_card(
                board_id="board1",
                column_id="col1",
                title="New Card",
                user_id="user1",
                custom_fields={"invalid_field": "value"}
            )

    def test_update_card_success(self):
        """Test successful card update."""
        card = Card(id="card1", column_id="col1", title="Original Title")
        self.board.cards = {"card1": card}
        
        result = self.service.update_card(
            board_id="board1",
            card_id="card1",
            user_id="user1",
            title="Updated Title",
            description="New description"
        )
        
        assert result.title == "Updated Title"
        assert result.description == "New description"

    def test_update_card_not_found(self):
        """Test card update fails when card doesn't exist."""
        with pytest.raises(NotFoundError, match="Card not found"):
            self.service.update_card(
                board_id="board1",
                card_id="nonexistent",
                user_id="user1",
                title="Updated Title"
            )

    def test_update_card_with_move(self):
        """Test card update with column move."""
        col1 = Column(id="col1", board_id="board1", name="Col1", position=0)
        col2 = Column(id="col2", board_id="board1", name="Col2", position=1)
        card = Card(id="card1", column_id="col1", title="Test Card")
        
        self.board.columns = {"col1": col1, "col2": col2}
        self.board.cards = {"card1": card}
        
        # Mock the internal move method
        self.core._internal_move.return_value = card
        
        result = self.service.update_card(
            board_id="board1",
            card_id="card1",
            user_id="user1",
            column_id="col2",
            title="Updated Title"
        )
        
        assert result.title == "Updated Title"
        self.core._internal_move.assert_called_once_with(
            self.board, "card1", "col2", None
        )

    def test_move_card_success(self):
        """Test successful card move."""
        card = Card(id="card1", column_id="col1", title="Test Card")
        self.board.cards = {"card1": card}
        self.core._internal_move.return_value = card
        
        result = self.service.move_card(
            board_id="board1",
            card_id="card1",
            to_column_id="col2",
            position=1,
            user_id="user1"
        )
        
        assert result == card
        self.core._internal_move.assert_called_once_with(
            self.board, "card1", "col2", 1
        )

    def test_delete_card_success(self):
        """Test successful card deletion."""
        col = Column(id="col1", board_id="board1", name="Col1", position=0)
        col.card_ids = ["card1"]
        card = Card(id="card1", column_id="col1", title="Test Card")
        
        self.board.columns = {"col1": col}
        self.board.cards = {"card1": card}
        
        self.service.delete_card(
            board_id="board1",
            card_id="card1",
            user_id="user1"
        )
        
        assert "card1" not in self.board.cards
        assert "card1" not in col.card_ids

    def test_delete_card_not_found(self):
        """Test card deletion fails when card doesn't exist."""
        with pytest.raises(NotFoundError, match="Card not found"):
            self.service.delete_card(
                board_id="board1",
                card_id="nonexistent",
                user_id="user1"
            )

    def test_block_card_dependency_success(self):
        """Test successful card blocking."""
        blocker = Card(id="card1", column_id="col1", title="Blocker")
        blocked = Card(id="card2", column_id="col1", title="Blocked")
        
        self.board.cards = {"card1": blocker, "card2": blocked}
        
        self.service.block_card_dependency(
            board_id="board1",
            blocking_card_id="card1",
            card_to_block_id="card2",
            user_id="user1"
        )
        
        assert "card2" in blocker.blocks
        assert "card1" in blocked.blocked_by

    def test_block_card_dependency_card_not_found(self):
        """Test card blocking fails when cards don't exist."""
        with pytest.raises(NotFoundError, match="One or both cards not found"):
            self.service.block_card_dependency(
                board_id="board1",
                blocking_card_id="nonexistent1",
                card_to_block_id="nonexistent2",
                user_id="user1"
            )

    def test_unblock_card_dependency_success(self):
        """Test successful card unblocking."""
        blocker = Card(id="card1", column_id="col1", title="Blocker")
        blocker.blocks = {"card2"}
        blocked = Card(id="card2", column_id="col1", title="Blocked")
        blocked.blocked_by = {"card1"}

        self.board.cards = {"card1": blocker, "card2": blocked}

        self.service.unblock_card_dependency(
            board_id="board1",
            blocking_card_id="card1",
            card_to_unblock_id="card2",
            user_id="user1"
        )

        assert "card2" not in blocker.blocks
        assert "card1" not in blocked.blocked_by

    def test_block_card_dependency_direct_circular(self):
        """Test blocking fails when it would create a direct circular dependency."""
        card1 = Card(id="card1", column_id="col1", title="Card 1")
        card2 = Card(id="card2", column_id="col1", title="Card 2")
        # card1 already blocks card2
        card1.blocks = {"card2"}
        card2.blocked_by = {"card1"}

        self.board.cards = {"card1": card1, "card2": card2}

        # Try to make card2 block card1 (would create cycle)
        with pytest.raises(ValidationError, match="circular dependency"):
            self.service.block_card_dependency(
                board_id="board1",
                blocking_card_id="card2",
                card_to_block_id="card1",
                user_id="user1"
            )

    def test_block_card_dependency_indirect_circular(self):
        """Test blocking fails when it would create an indirect circular dependency."""
        card1 = Card(id="card1", column_id="col1", title="Card 1")
        card2 = Card(id="card2", column_id="col1", title="Card 2")
        card3 = Card(id="card3", column_id="col1", title="Card 3")

        # Create chain: card1 blocks card2, card2 blocks card3
        card1.blocks = {"card2"}
        card2.blocked_by = {"card1"}
        card2.blocks = {"card3"}
        card3.blocked_by = {"card2"}

        self.board.cards = {"card1": card1, "card2": card2, "card3": card3}

        # Try to make card3 block card1 (would create cycle: card1 -> card2 -> card3 -> card1)
        with pytest.raises(ValidationError, match="circular dependency"):
            self.service.block_card_dependency(
                board_id="board1",
                blocking_card_id="card3",
                card_to_block_id="card1",
                user_id="user1"
            )

    def test_block_card_dependency_self_blocking(self):
        """Test blocking fails when trying to block a card with itself."""
        card1 = Card(id="card1", column_id="col1", title="Card 1")

        self.board.cards = {"card1": card1}

        # Try to make card1 block itself
        with pytest.raises(ValidationError, match="circular dependency"):
            self.service.block_card_dependency(
                board_id="board1",
                blocking_card_id="card1",
                card_to_block_id="card1",
                user_id="user1"
            )

    def test_block_card_dependency_complex_chain_allowed(self):
        """Test blocking is allowed when it doesn't create a cycle."""
        card1 = Card(id="card1", column_id="col1", title="Card 1")
        card2 = Card(id="card2", column_id="col1", title="Card 2")
        card3 = Card(id="card3", column_id="col1", title="Card 3")
        card4 = Card(id="card4", column_id="col1", title="Card 4")

        # Create chain: card1 blocks card2, card3 blocks card4
        card1.blocks = {"card2"}
        card2.blocked_by = {"card1"}
        card3.blocks = {"card4"}
        card4.blocked_by = {"card3"}

        self.board.cards = {
            "card1": card1,
            "card2": card2,
            "card3": card3,
            "card4": card4
        }

        # This should succeed: card2 can block card3 (no cycle)
        self.service.block_card_dependency(
            board_id="board1",
            blocking_card_id="card2",
            card_to_block_id="card3",
            user_id="user1"
        )

        assert "card3" in card2.blocks
        assert "card2" in card3.blocked_by