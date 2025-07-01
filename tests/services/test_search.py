"""Tests for search service functionality."""

from datetime import datetime, timezone

import pytest

from kanban import Board, Card, InMemoryCardSearcher


class TestInMemoryCardSearcher:
    """Test card search functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.board = Board(
            id="board1",
            name="Test Board",
            owner_id="user1",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        
        # Add some test cards
        self.card1 = Card(
            id="card1",
            column_id="col1",
            title="First Card",
            description="This is the first card",
            assignee_ids={"user1", "user2"},
            custom_fields={"labels": {"urgent", "frontend"}},
        )
        
        self.card2 = Card(
            id="card2",
            column_id="col1",
            title="Second Card",
            description="Another card for testing",
            assignee_ids={"user2"},
            custom_fields={"labels": {"backend"}},
            blocked_by={"card3"},
        )
        
        self.card3 = Card(
            id="card3",
            column_id="col2",
            title="Third Card",
            description="Yet another card",
            assignee_ids={"user3"},
            custom_fields={},
        )
        
        self.board.cards = {
            "card1": self.card1,
            "card2": self.card2,
            "card3": self.card3,
        }
        
        self.searcher = InMemoryCardSearcher()

    def test_search_no_filters_returns_all_cards(self):
        """Test search with no filters returns all cards."""
        results = self.searcher.search(self.board)
        assert len(results) == 3
        assert set(c.id for c in results) == {"card1", "card2", "card3"}

    def test_search_by_text_in_title(self):
        """Test search by text in card title."""
        results = self.searcher.search(self.board, text="First")
        assert len(results) == 1
        assert results[0].id == "card1"

    def test_search_by_text_in_description(self):
        """Test search by text in card description."""
        results = self.searcher.search(self.board, text="testing")
        assert len(results) == 1
        assert results[0].id == "card2"

    def test_search_by_text_case_insensitive(self):
        """Test search is case insensitive."""
        results = self.searcher.search(self.board, text="FIRST")
        assert len(results) == 1
        assert results[0].id == "card1"

    def test_search_by_labels_subset_match(self):
        """Test search by labels finds cards with required labels."""
        results = self.searcher.search(self.board, labels=["urgent"])
        assert len(results) == 1
        assert results[0].id == "card1"

    def test_search_by_labels_multiple_required(self):
        """Test search by multiple labels requires all labels."""
        results = self.searcher.search(self.board, labels=["urgent", "frontend"])
        assert len(results) == 1
        assert results[0].id == "card1"

    def test_search_by_labels_no_match(self):
        """Test search by labels that don't exist."""
        results = self.searcher.search(self.board, labels=["nonexistent"])
        assert len(results) == 0

    def test_search_by_assignee_ids(self):
        """Test search by assignee IDs."""
        results = self.searcher.search(self.board, assignee_ids={"user1"})
        assert len(results) == 1
        assert results[0].id == "card1"

    def test_search_by_assignee_ids_intersection(self):
        """Test search by assignee IDs with intersection."""
        results = self.searcher.search(self.board, assignee_ids={"user2"})
        assert len(results) == 2
        assert set(c.id for c in results) == {"card1", "card2"}

    def test_search_by_is_blocked_true(self):
        """Test search for blocked cards."""
        results = self.searcher.search(self.board, is_blocked=True)
        assert len(results) == 1
        assert results[0].id == "card2"

    def test_search_by_is_blocked_false(self):
        """Test search for non-blocked cards."""
        results = self.searcher.search(self.board, is_blocked=False)
        assert len(results) == 2
        assert set(c.id for c in results) == {"card1", "card3"}

    def test_search_combined_filters(self):
        """Test search with multiple filters combined."""
        results = self.searcher.search(
            self.board,
            text="card",
            assignee_ids={"user2"},
            is_blocked=False
        )
        assert len(results) == 1
        assert results[0].id == "card1"