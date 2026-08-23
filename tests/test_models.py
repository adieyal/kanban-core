"""Tests for kanban models."""

from datetime import datetime, timedelta, timezone

import pytest

from kanban import ValidationError
from kanban.models import Board, Card, Column, ColumnPolicy, CustomField, FieldType


class TestCard:
    """Test Card model functionality."""

    def test_card_creation(self):
        """Test basic card creation."""
        card = Card(id="card1", column_id="col1", title="Test Card")
        assert card.id == "card1"
        assert card.column_id == "col1"
        assert card.title == "Test Card"
        assert not card.is_blocked()

    def test_card_blocking(self):
        """Test card blocking functionality."""
        card = Card(id="card1", column_id="col1")
        assert not card.is_blocked()

        card.blocked_by.add("card2")
        assert card.is_blocked()

    def test_add_time_in_column(self):
        """Test time tracking in columns."""
        card = Card(id="card1", column_id="col1")
        duration = timedelta(hours=2)

        card.add_time_in_column("col1", duration)
        assert card.time_in_column["col1"] == duration

        # Add more time
        card.add_time_in_column("col1", duration)
        assert card.time_in_column["col1"] == timedelta(hours=4)

    def test_card_to_dict(self):
        """Test card serialization."""
        now = datetime.now(timezone.utc)
        card = Card(
            id="card1",
            column_id="col1",
            title="Test Card",
            created_at=now,
            assignee_ids={"user1", "user2"},
        )

        card_dict = card.to_dict()
        assert card_dict["id"] == "card1"
        assert card_dict["title"] == "Test Card"
        assert "user1" in card_dict["assignee_ids"]
        assert card_dict["created_at"] == now.isoformat()


class TestColumn:
    """Test Column model functionality."""

    def test_column_creation(self):
        """Test basic column creation."""
        column = Column(id="col1", board_id="board1", name="To Do")
        assert column.id == "col1"
        assert column.board_id == "board1"
        assert column.name == "To Do"

    def test_can_accept_card_wip_limit(self):
        """Test WIP limit checking."""
        policy = ColumnPolicy(wip_limit=2)
        column = Column(id="col1", board_id="board1", policy=policy)
        column.card_ids = ["card1", "card2"]  # At limit

        card = Card(id="card3", column_id="other_col")

        # Should reject new entry (at limit)
        can_accept, reason = column.can_accept_card(card, is_new_entry=True)
        assert not can_accept
        assert "WIP limit" in reason

        # Should accept existing card (not new entry)
        can_accept, reason = column.can_accept_card(card, is_new_entry=False)
        assert can_accept

    def test_can_accept_card_entry_criteria(self):
        """Test entry criteria checking."""
        policy = ColumnPolicy(
            entry_criteria=lambda card: (
                "ready" in card.custom_fields.get("labels", set())
            )
        )
        column = Column(id="col1", board_id="board1", policy=policy)

        # Card without ready label
        card1 = Card(id="card1", column_id="other_col")
        can_accept, reason = column.can_accept_card(card1, is_new_entry=True)
        assert not can_accept
        assert "entry criteria" in reason

        # Card with ready label
        card2 = Card(
            id="card2", column_id="other_col", custom_fields={"labels": {"ready"}}
        )
        can_accept, reason = column.can_accept_card(card2, is_new_entry=True)
        assert can_accept


class TestBoard:
    """Test Board model functionality."""

    def test_board_creation(self):
        """Test basic board creation."""
        board = Board(id="board1", name="Test Board")
        assert board.id == "board1"
        assert board.name == "Test Board"

    def test_get_columns_ordered(self):
        """Test getting columns in order."""
        board = Board(id="board1")
        col1 = Column(id="col1", board_id="board1", name="Col 1", position=2)
        col2 = Column(id="col2", board_id="board1", name="Col 2", position=0)
        col3 = Column(id="col3", board_id="board1", name="Col 3", position=1)

        board.columns = {"col1": col1, "col2": col2, "col3": col3}

        ordered = board.get_columns_ordered()
        assert len(ordered) == 3
        assert ordered[0].name == "Col 2"  # position 0
        assert ordered[1].name == "Col 3"  # position 1
        assert ordered[2].name == "Col 1"  # position 2

    def test_get_cards_in_column(self):
        """Test getting cards in a specific column."""
        board = Board(id="board1")
        column = Column(
            id="col1", board_id="board1", card_ids=["card1", "card2", "card3"]
        )
        board.columns["col1"] = column

        card1 = Card(id="card1", column_id="col1")
        card2 = Card(id="card2", column_id="col1")
        # card3 not in board.cards - should be skipped
        board.cards = {"card1": card1, "card2": card2}

        cards = board.get_cards_in_column("col1")
        assert len(cards) == 2
        assert cards[0].id == "card1"
        assert cards[1].id == "card2"

        # Non-existent column
        assert board.get_cards_in_column("nonexistent") == []


class TestCustomField:
    """Test CustomField functionality."""

    def test_custom_field_creation(self):
        """Test custom field creation."""
        field = CustomField(
            name="priority",
            field_type=FieldType.SELECT,
            options=["low", "medium", "high"],
            required=True,
        )
        assert field.name == "priority"
        assert field.field_type == FieldType.SELECT
        assert field.required is True

    def test_validate_missing_validator(self):
        """Test validation with missing validator."""
        field = CustomField(
            name="test",
            field_type=FieldType.TEXT,
            validator_ids=["nonexistent_validator"],
        )

        with pytest.raises(ValidationError, match="Unknown validator"):
            field.validate("test_value")
