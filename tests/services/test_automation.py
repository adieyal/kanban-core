"""Tests for automation service functionality."""

import copy
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest

from kanban import AutomationRule, Board, Event, KanbanError, SyncAutomationRunner
from kanban.services import AutomationContext, _KanbanServiceCore


class TestSyncAutomationRunner:
    """Test automation execution."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = SyncAutomationRunner()
        self.board = Board(
            id="board1",
            name="Test Board",
            owner_id="user1",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.service_core = Mock(spec=_KanbanServiceCore)
        self.event = Event(
            type="card.created",
            entity_id="card1",
            entity_type="card",
            id="event1",
            timestamp=datetime.now(timezone.utc),
        )

    def test_run_no_rules_returns_false(self):
        """Test running automation with no rules returns false."""
        context = AutomationContext()
        result = self.runner.run(self.board, self.event, self.service_core, context)
        assert result is False

    def test_run_disabled_rule_not_executed(self):
        """Test disabled automation rules are not executed."""
        rule = Mock(spec=AutomationRule)
        rule.enabled = False
        rule.trigger.return_value = True
        
        self.board.automation_rules = [rule]
        context = AutomationContext()
        
        result = self.runner.run(self.board, self.event, self.service_core, context)
        
        assert result is False
        rule.action.assert_not_called()

    def test_run_rule_trigger_false_not_executed(self):
        """Test automation rules with false trigger are not executed."""
        rule = Mock(spec=AutomationRule)
        rule.enabled = True
        rule.trigger.return_value = False
        
        self.board.automation_rules = [rule]
        context = AutomationContext()
        
        result = self.runner.run(self.board, self.event, self.service_core, context)
        
        assert result is False
        rule.action.assert_not_called()

    def test_run_rule_executed_when_enabled_and_triggered(self):
        """Test automation rule is executed when enabled and triggered."""
        rule = Mock(spec=AutomationRule)
        rule.enabled = True
        rule.trigger.return_value = True
        
        self.board.automation_rules = [rule]
        context = AutomationContext()
        
        # Mock snapshot_board to detect changes
        with patch('kanban.services.automation.snapshot_board') as mock_snapshot:
            # First call returns original board state, second call after action returns modified state
            original_board = copy.deepcopy(self.board)
            modified_board = copy.deepcopy(self.board)
            modified_board.name = "Modified"  # Simulate modification
            mock_snapshot.side_effect = [original_board, modified_board]
            
            result = self.runner.run(self.board, self.event, self.service_core, context)
        
        assert result is True
        rule.action.assert_called_once_with(
            self.event, self.board, self.service_core, context
        )

    def test_run_prevents_duplicate_event_processing(self):
        """Test automation prevents processing the same event twice."""
        rule = Mock(spec=AutomationRule)
        rule.enabled = True
        rule.trigger.return_value = True
        
        self.board.automation_rules = [rule]
        context = AutomationContext()
        context.processed_event_ids.add("event1")
        
        result = self.runner.run(self.board, self.event, self.service_core, context)
        
        assert result is False
        rule.action.assert_not_called()

    def test_run_chain_limit_exceeded_raises_error(self):
        """Test automation chain limit prevents infinite loops."""
        context = AutomationContext()
        # Simulate exceeding the chain limit
        for i in range(SyncAutomationRunner.MAX_CHAIN):
            context.processed_event_ids.add(f"event{i}")
        
        with pytest.raises(KanbanError, match="Automation chain limit exceeded"):
            self.runner.run(self.board, self.event, self.service_core, context)

    def test_run_multiple_rules_executed(self):
        """Test multiple automation rules are executed."""
        rule1 = Mock(spec=AutomationRule)
        rule1.enabled = True
        rule1.trigger.return_value = True
        
        rule2 = Mock(spec=AutomationRule)
        rule2.enabled = True
        rule2.trigger.return_value = True
        
        self.board.automation_rules = [rule1, rule2]
        context = AutomationContext()
        
        with patch('kanban.services.automation.snapshot_board') as mock_snapshot:
            # Simulate changes for both rules
            original_board = copy.deepcopy(self.board)
            modified_board1 = copy.deepcopy(self.board)
            modified_board1.name = "Modified1"
            modified_board2 = copy.deepcopy(self.board) 
            modified_board2.name = "Modified2"
            mock_snapshot.side_effect = [original_board, modified_board1, modified_board2]
            
            result = self.runner.run(self.board, self.event, self.service_core, context)
        
        assert result is True
        rule1.action.assert_called_once()
        rule2.action.assert_called_once()