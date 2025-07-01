"""Tests for automation rules and automation system."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from kanban import (
    Board,
    Card,
    Column,
    Event,
    ValidationError,
    create_auto_move_rule,
    create_due_date_warning_rule,
)


class TestAutoMoveRule:
    """Test auto-move automation rule functionality."""

    def test_create_auto_move_rule(self):
        """Test creating an auto-move rule."""
        rule = create_auto_move_rule("ready", "In Progress")
        
        assert rule.id == "auto-move-ready-to-In Progress"
        assert rule.name == "Auto-move 'ready' to In Progress"
        assert rule.enabled is True
        assert rule.trigger is not None
        assert rule.action is not None

    def test_auto_move_trigger_conditions(self):
        """Test auto-move rule trigger conditions."""
        rule = create_auto_move_rule("ready", "In Progress")
        
        # Should trigger on card.updated with custom_fields
        event_updated = Event(
            type="card.updated",
            entity_id="card1",
            entity_type="card",
            id="event1",
            timestamp=datetime.now(timezone.utc),
            data={"custom_fields": {"labels": {"ready"}}}
        )
        assert rule.trigger(event_updated) is True
        
        # Should not trigger on other event types
        event_created = Event(
            type="card.created",
            entity_id="card1",
            entity_type="card",
            id="event2",
            timestamp=datetime.now(timezone.utc),
            data={"custom_fields": {"labels": {"ready"}}}
        )
        assert rule.trigger(event_created) is False
        
        # Should not trigger without custom_fields in data
        event_no_fields = Event(
            type="card.updated",
            entity_id="card1",
            entity_type="card",
            id="event3",
            timestamp=datetime.now(timezone.utc),
            data={}
        )
        assert rule.trigger(event_no_fields) is False

    def test_auto_move_action_successful_move(self):
        """Test auto-move action when conditions are met."""
        rule = create_auto_move_rule("ready", "In Progress")
        
        # Create board with columns
        board = Board(id="board1")
        todo_col = Column(id="col1", board_id="board1", name="To Do")
        progress_col = Column(id="col2", board_id="board1", name="In Progress")
        board.columns = {"col1": todo_col, "col2": progress_col}
        
        # Create card with ready label
        card = Card(
            id="card1",
            column_id="col1",
            custom_fields={"labels": {"ready"}}
        )
        board.cards = {"card1": card}
        todo_col.card_ids = ["card1"]
        
        # Create mock service core with _internal_move method
        service_core = Mock()
        context = Mock()
        
        event = Event(
            type="card.updated",
            entity_id="card1",
            entity_type="card",
            id="event1",
            timestamp=datetime.now(timezone.utc),
            data={"custom_fields": {"labels": {"ready"}}}
        )
        
        # Execute action
        rule.action(event, board, service_core, context)
        
        # Verify _internal_move was called
        service_core._internal_move.assert_called_once_with(board, "card1", "col2")

    def test_auto_move_action_no_matching_label(self):
        """Test auto-move action when card doesn't have matching label."""
        rule = create_auto_move_rule("ready", "In Progress")
        
        board = Board(id="board1")
        progress_col = Column(id="col2", board_id="board1", name="In Progress")
        board.columns = {"col2": progress_col}
        
        # Card without ready label
        card = Card(
            id="card1",
            column_id="col1",
            custom_fields={"labels": {"other"}}
        )
        board.cards = {"card1": card}
        
        service_core = Mock()
        context = Mock()
        
        event = Event(
            type="card.updated",
            entity_id="card1",
            entity_type="card",
            id="event1",
            timestamp=datetime.now(timezone.utc),
            data={}
        )
        
        # Execute action - should not call _internal_move
        rule.action(event, board, service_core, context)
        service_core._internal_move.assert_not_called()

    def test_auto_move_action_missing_column(self):
        """Test auto-move action when target column doesn't exist."""
        rule = create_auto_move_rule("ready", "Nonexistent Column")
        
        board = Board(id="board1")
        card = Card(
            id="card1",
            column_id="col1",
            custom_fields={"labels": {"ready"}}
        )
        board.cards = {"card1": card}
        
        service_core = Mock()
        context = Mock()
        
        event = Event(
            type="card.updated",
            entity_id="card1",
            entity_type="card",
            id="event1",
            timestamp=datetime.now(timezone.utc),
            data={}
        )
        
        # Execute action - should not call _internal_move
        rule.action(event, board, service_core, context)
        service_core._internal_move.assert_not_called()

    def test_auto_move_action_card_already_in_target(self):
        """Test auto-move action when card is already in target column."""
        rule = create_auto_move_rule("ready", "In Progress")
        
        board = Board(id="board1")
        progress_col = Column(id="col2", board_id="board1", name="In Progress")
        board.columns = {"col2": progress_col}
        
        # Card already in target column
        card = Card(
            id="card1",
            column_id="col2",  # Already in progress
            custom_fields={"labels": {"ready"}}
        )
        board.cards = {"card1": card}
        
        service_core = Mock()
        context = Mock()
        
        event = Event(
            type="card.updated",
            entity_id="card1",
            entity_type="card",
            id="event1",
            timestamp=datetime.now(timezone.utc),
            data={}
        )
        
        # Execute action - should not call _internal_move
        rule.action(event, board, service_core, context)
        service_core._internal_move.assert_not_called()

    def test_auto_move_action_validation_error_handling(self):
        """Test auto-move action handles ValidationError gracefully."""
        rule = create_auto_move_rule("ready", "In Progress")
        
        board = Board(id="board1")
        progress_col = Column(id="col2", board_id="board1", name="In Progress")
        board.columns = {"col2": progress_col}
        
        card = Card(
            id="card1",
            column_id="col1",
            custom_fields={"labels": {"ready"}}
        )
        board.cards = {"card1": card}
        
        # Mock service core to raise ValidationError
        service_core = Mock()
        service_core._internal_move.side_effect = ValidationError("WIP limit exceeded")
        context = Mock()
        
        event = Event(
            type="card.updated",
            entity_id="card1",
            entity_type="card",
            id="event1",
            timestamp=datetime.now(timezone.utc),
            data={}
        )
        
        # Should not raise exception
        rule.action(event, board, service_core, context)
        service_core._internal_move.assert_called_once()


class TestDueDateWarningRule:
    """Test due date warning automation rule functionality."""

    def test_create_due_date_warning_rule(self):
        """Test creating a due date warning rule."""
        rule = create_due_date_warning_rule(3)
        
        assert rule.id == "due-date-warning-3-days"
        assert rule.name == "Due date warning (3 days)"
        assert rule.enabled is True
        assert rule.trigger is not None
        assert rule.action is not None

    def test_due_date_trigger_conditions(self):
        """Test due date warning rule trigger conditions."""
        rule = create_due_date_warning_rule()
        
        # Should trigger on card.created
        event_created = Event(
            type="card.created",
            entity_id="card1",
            entity_type="card",
            id="event1",
            timestamp=datetime.now(timezone.utc)
        )
        assert rule.trigger(event_created) is True
        
        # Should trigger on card.updated
        event_updated = Event(
            type="card.updated",
            entity_id="card1",
            entity_type="card",
            id="event2",
            timestamp=datetime.now(timezone.utc)
        )
        assert rule.trigger(event_updated) is True
        
        # Should not trigger on other events
        event_other = Event(
            type="card.moved",
            entity_id="card1",
            entity_type="card",
            id="event3",
            timestamp=datetime.now(timezone.utc)
        )
        assert rule.trigger(event_other) is False

    def test_due_date_action_add_warning_label(self):
        """Test adding due-soon label when deadline approaches."""
        rule = create_due_date_warning_rule(3)
        
        board = Board(id="board1")
        
        # Create card with due date in 2 days (within threshold)
        due_date = datetime.now(timezone.utc) + timedelta(days=2)
        card = Card(
            id="card1",
            column_id="col1",
            due_date=due_date,
            custom_fields={"labels": set()}
        )
        board.cards = {"card1": card}
        
        # Mock service core clock
        service_core = Mock()
        service_core.clock.return_value = datetime.now(timezone.utc)
        context = Mock()
        
        event = Event(
            type="card.updated",
            entity_id="card1",
            entity_type="card",
            id="event1",
            timestamp=datetime.now(timezone.utc)
        )
        
        # Execute action
        rule.action(event, board, service_core, context)
        
        # Verify label was added
        assert "due-soon" in card.custom_fields["labels"]
        assert card.updated_at is not None

    def test_due_date_action_remove_warning_label(self):
        """Test removing due-soon label when deadline is far away."""
        rule = create_due_date_warning_rule(3)
        
        board = Board(id="board1")
        
        # Create card with due date in 5 days (beyond threshold)
        due_date = datetime.now(timezone.utc) + timedelta(days=5)
        card = Card(
            id="card1",
            column_id="col1",
            due_date=due_date,
            custom_fields={"labels": {"due-soon", "other"}}
        )
        board.cards = {"card1": card}
        
        service_core = Mock()
        service_core.clock.return_value = datetime.now(timezone.utc)
        context = Mock()
        
        event = Event(
            type="card.updated",
            entity_id="card1",
            entity_type="card",
            id="event1",
            timestamp=datetime.now(timezone.utc)
        )
        
        # Execute action
        rule.action(event, board, service_core, context)
        
        # Verify label was removed but others remain
        assert "due-soon" not in card.custom_fields["labels"]
        assert "other" in card.custom_fields["labels"]

    def test_due_date_action_no_due_date(self):
        """Test action when card has no due date."""
        rule = create_due_date_warning_rule(3)
        
        board = Board(id="board1")
        card = Card(
            id="card1",
            column_id="col1",
            due_date=None,
            custom_fields={"labels": set()}
        )
        board.cards = {"card1": card}
        
        service_core = Mock()
        context = Mock()
        
        event = Event(
            type="card.updated",
            entity_id="card1",
            entity_type="card",
            id="event1",
            timestamp=datetime.now(timezone.utc)
        )
        
        original_labels = card.custom_fields["labels"].copy()
        
        # Execute action
        rule.action(event, board, service_core, context)
        
        # Labels should be unchanged
        assert card.custom_fields["labels"] == original_labels

    def test_due_date_action_archived_card(self):
        """Test action doesn't process archived cards."""
        rule = create_due_date_warning_rule(3)
        
        board = Board(id="board1")
        
        due_date = datetime.now(timezone.utc) + timedelta(days=1)
        card = Card(
            id="card1",
            column_id="col1",
            due_date=due_date,
            archived=True,  # Archived card
            custom_fields={"labels": set()}
        )
        board.cards = {"card1": card}
        
        service_core = Mock()
        context = Mock()
        
        event = Event(
            type="card.updated",
            entity_id="card1",
            entity_type="card",
            id="event1",
            timestamp=datetime.now(timezone.utc)
        )
        
        original_labels = card.custom_fields["labels"].copy()
        
        # Execute action
        rule.action(event, board, service_core, context)
        
        # Labels should be unchanged for archived cards
        assert card.custom_fields["labels"] == original_labels

    def test_due_date_action_missing_card(self):
        """Test action when referenced card doesn't exist."""
        rule = create_due_date_warning_rule(3)
        
        board = Board(id="board1")
        board.cards = {}  # No cards
        
        service_core = Mock()
        context = Mock()
        
        event = Event(
            type="card.updated",
            entity_id="nonexistent",
            entity_type="card",
            id="event1",
            timestamp=datetime.now(timezone.utc)
        )
        
        # Should not raise exception
        rule.action(event, board, service_core, context)