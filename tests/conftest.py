"""Pytest configuration and shared fixtures."""

import pytest

from kanban import SimpleKanban


@pytest.fixture
def kanban():
    """Create a fresh SimpleKanban instance for testing."""
    return SimpleKanban()


@pytest.fixture
def board_with_cards(kanban):
    """Create a board with some test cards."""
    board = kanban.create_board("test_user", "Test Board")

    # Add some test cards
    card1 = kanban.add_card("test_user", board.id, "To Do", "Task 1")
    card2 = kanban.add_card("test_user", board.id, "To Do", "Task 2")
    card3 = kanban.add_card("test_user", board.id, "In Progress", "Task 3")

    return {"board": board, "cards": [card1, card2, card3], "kanban": kanban}
