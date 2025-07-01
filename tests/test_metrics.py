"""Tests for metrics calculation functionality."""

from datetime import datetime, timedelta, timezone

from kanban import (
    Board,
    Card,
    Column,
    Event,
    MetricsCalculator,
    TwentyFourSevenCalendar,
)


class TestTwentyFourSevenCalendar:
    """Test 24/7 calendar implementation."""

    def test_working_seconds_between_positive_difference(self):
        """Test calculating working seconds with positive time difference."""
        calendar = TwentyFourSevenCalendar()
        
        start = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        end = datetime(2023, 1, 1, 12, 30, 0, tzinfo=timezone.utc)
        
        result = calendar.working_seconds_between(start, end)
        
        # 2.5 hours = 9000 seconds
        assert result == 9000

    def test_working_seconds_between_negative_difference(self):
        """Test calculating working seconds with negative time difference."""
        calendar = TwentyFourSevenCalendar()
        
        start = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        end = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        
        result = calendar.working_seconds_between(start, end)
        
        # Should return 0 for negative differences
        assert result == 0

    def test_working_seconds_between_same_time(self):
        """Test calculating working seconds with same start and end time."""
        calendar = TwentyFourSevenCalendar()
        
        time = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        
        result = calendar.working_seconds_between(time, time)
        
        assert result == 0

    def test_working_seconds_between_large_difference(self):
        """Test calculating working seconds with large time difference."""
        calendar = TwentyFourSevenCalendar()
        
        start = datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2023, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
        
        result = calendar.working_seconds_between(start, end)
        
        # 24 hours = 86400 seconds
        assert result == 86400


class TestMetricsCalculator:
    """Test metrics calculation methods."""

    def test_calculate_wip_empty_board(self):
        """Test WIP calculation with empty board."""
        board = Board(id="board1")
        
        result = MetricsCalculator.calculate_wip(board)
        
        assert result == {}

    def test_calculate_wip_with_columns(self):
        """Test WIP calculation with columns containing cards."""
        board = Board(id="board1")
        
        # Create columns with different numbers of cards
        col1 = Column(id="col1", board_id="board1", card_ids=["card1", "card2"])
        col2 = Column(id="col2", board_id="board1", card_ids=["card3"])
        col3 = Column(id="col3", board_id="board1", card_ids=[])
        
        board.columns = {"col1": col1, "col2": col2, "col3": col3}
        
        result = MetricsCalculator.calculate_wip(board)
        
        assert result == {"col1": 2, "col2": 1, "col3": 0}

    def test_calculate_cycle_time_no_time_data(self):
        """Test cycle time calculation with card having no time data."""
        card = Card(id="card1", column_id="col1")
        done_columns = {"done_col"}
        calendar = TwentyFourSevenCalendar()
        
        result = MetricsCalculator.calculate_cycle_time(card, done_columns, calendar)
        
        assert result == 0

    def test_calculate_cycle_time_with_time_data(self):
        """Test cycle time calculation with card having time data."""
        created_time = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        
        card = Card(
            id="card1",
            column_id="col1",
            created_at=created_time,
            time_in_column={
                "done_col": timedelta(hours=2),
                "other_col": timedelta(hours=1)  # Should be ignored
            }
        )
        
        done_columns = {"done_col"}
        calendar = TwentyFourSevenCalendar()
        
        result = MetricsCalculator.calculate_cycle_time(card, done_columns, calendar)
        
        # 2 hours = 7200 seconds
        assert result == 7200

    def test_calculate_cycle_time_multiple_done_columns(self):
        """Test cycle time calculation with multiple done columns."""
        created_time = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        
        card = Card(
            id="card1",
            column_id="col1",
            created_at=created_time,
            time_in_column={
                "done_col1": timedelta(hours=1),
                "done_col2": timedelta(hours=1.5),
                "in_progress": timedelta(hours=3)  # Should be ignored
            }
        )
        
        done_columns = {"done_col1", "done_col2"}
        calendar = TwentyFourSevenCalendar()
        
        result = MetricsCalculator.calculate_cycle_time(card, done_columns, calendar)
        
        # 1 + 1.5 = 2.5 hours = 9000 seconds
        assert result == 9000

    def test_calculate_cycle_time_no_created_at_uses_entered_column_at(self):
        """Test cycle time uses entered_column_at when created_at is missing."""
        entered_time = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        
        card = Card(
            id="card1",
            column_id="col1",
            created_at=None,
            entered_column_at=entered_time,
            time_in_column={"done_col": timedelta(hours=1)}
        )
        
        done_columns = {"done_col"}
        calendar = TwentyFourSevenCalendar()
        
        result = MetricsCalculator.calculate_cycle_time(card, done_columns, calendar)
        
        # 1 hour = 3600 seconds
        assert result == 3600

    def test_calculate_lead_time_with_created_at(self):
        """Test lead time calculation with created_at timestamp."""
        created_time = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        card = Card(
            id="card1",
            column_id="col1",
            created_at=created_time
        )
        
        calendar = TwentyFourSevenCalendar()
        
        result = MetricsCalculator.calculate_lead_time(card, now, calendar)
        
        # 2 hours difference
        assert result == timedelta(hours=2)

    def test_calculate_lead_time_without_created_at(self):
        """Test lead time calculation without created_at timestamp."""
        card = Card(id="card1", column_id="col1", created_at=None)
        now = datetime.now(timezone.utc)
        calendar = TwentyFourSevenCalendar()
        
        result = MetricsCalculator.calculate_lead_time(card, now, calendar)
        
        assert result == timedelta()

    def test_calculate_throughput_empty_events(self):
        """Test throughput calculation with no events."""
        events = []
        done_columns = {"done"}
        
        result = MetricsCalculator.calculate_throughput(events, done_columns)
        
        assert result == 0.0

    def test_calculate_throughput_with_completed_cards(self):
        """Test throughput calculation with completed cards."""
        now = datetime.now(timezone.utc)
        
        # Events within the period (default 7 days)
        recent_event1 = Event(
            type="card.moved",
            entity_id="card1",
            entity_type="card",
            id="event1",
            timestamp=now - timedelta(days=2),
            data={"to_column_id": "done"}
        )
        
        recent_event2 = Event(
            type="card.moved",
            entity_id="card2",
            entity_type="card",
            id="event2",
            timestamp=now - timedelta(days=1),
            data={"to_column_id": "done"}
        )
        
        # Event outside the period
        old_event = Event(
            type="card.moved",
            entity_id="card3",
            entity_type="card",
            id="event3",
            timestamp=now - timedelta(days=10),
            data={"to_column_id": "done"}
        )
        
        events = [recent_event1, recent_event2, old_event]
        done_columns = {"done"}
        
        result = MetricsCalculator.calculate_throughput(
            events, done_columns, period_days=7, now=now
        )
        
        # 2 cards completed in 7 days = 2/7 ≈ 0.286
        assert abs(result - (2/7)) < 0.001

    def test_calculate_throughput_different_period(self):
        """Test throughput calculation with different time period."""
        now = datetime.now(timezone.utc)
        
        event = Event(
            type="card.moved",
            entity_id="card1",
            entity_type="card",
            id="event1",
            timestamp=now - timedelta(days=1),
            data={"to_column_id": "done"}
        )
        
        events = [event]
        done_columns = {"done"}
        
        result = MetricsCalculator.calculate_throughput(
            events, done_columns, period_days=2, now=now
        )
        
        # 1 card in 2 days = 0.5
        assert result == 0.5

    def test_calculate_throughput_wrong_event_type(self):
        """Test throughput calculation ignores non-move events."""
        now = datetime.now(timezone.utc)
        
        event = Event(
            type="card.created",  # Not a move event
            entity_id="card1",
            entity_type="card",
            id="event1",
            timestamp=now - timedelta(days=1),
            data={"to_column_id": "done"}
        )
        
        events = [event]
        done_columns = {"done"}
        
        result = MetricsCalculator.calculate_throughput(events, done_columns, now=now)
        
        assert result == 0.0

    def test_calculate_throughput_wrong_target_column(self):
        """Test throughput calculation ignores moves to non-done columns."""
        now = datetime.now(timezone.utc)
        
        event = Event(
            type="card.moved",
            entity_id="card1",
            entity_type="card",
            id="event1",
            timestamp=now - timedelta(days=1),
            data={"to_column_id": "in_progress"}  # Not a done column
        )
        
        events = [event]
        done_columns = {"done"}
        
        result = MetricsCalculator.calculate_throughput(events, done_columns, now=now)
        
        assert result == 0.0

    def test_calculate_throughput_zero_period_days(self):
        """Test throughput calculation with zero period days."""
        now = datetime.now(timezone.utc)
        
        event = Event(
            type="card.moved",
            entity_id="card1",
            entity_type="card",
            id="event1",
            timestamp=now,
            data={"to_column_id": "done"}
        )
        
        events = [event]
        done_columns = {"done"}
        
        result = MetricsCalculator.calculate_throughput(
            events, done_columns, period_days=0, now=now
        )
        
        assert result == 0.0

    def test_calculate_throughput_multiple_done_columns(self):
        """Test throughput calculation with multiple done columns."""
        now = datetime.now(timezone.utc)
        
        event1 = Event(
            type="card.moved",
            entity_id="card1",
            entity_type="card",
            id="event1",
            timestamp=now - timedelta(days=1),
            data={"to_column_id": "done"}
        )
        
        event2 = Event(
            type="card.moved",
            entity_id="card2",
            entity_type="card",
            id="event2",
            timestamp=now - timedelta(days=2),
            data={"to_column_id": "completed"}
        )
        
        events = [event1, event2]
        done_columns = {"done", "completed"}
        
        result = MetricsCalculator.calculate_throughput(
            events, done_columns, period_days=7, now=now
        )
        
        # 2 cards in 7 days = 2/7
        assert abs(result - (2/7)) < 0.001

    def test_calculate_throughput_default_now(self):
        """Test throughput calculation uses current time when now is None."""
        # Create an event that's definitely recent
        recent_time = datetime.now(timezone.utc) - timedelta(minutes=30)
        
        event = Event(
            type="card.moved",
            entity_id="card1",
            entity_type="card",
            id="event1",
            timestamp=recent_time,
            data={"to_column_id": "done"}
        )
        
        events = [event]
        done_columns = {"done"}
        
        # Don't pass 'now' parameter
        result = MetricsCalculator.calculate_throughput(events, done_columns, period_days=1)
        
        # Should find the recent event and calculate throughput
        assert result == 1.0  # 1 card in 1 day