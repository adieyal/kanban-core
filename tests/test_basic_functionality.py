"""Basic functionality tests for the Kanban library."""

from kanban import Board, Card, SimpleKanban


class TestBasicFunctionality:
    """Test basic kanban functionality."""

    def test_create_board(self):
        """Test board creation."""
        kanban = SimpleKanban()
        board = kanban.create_board("test_user", "Test Board")

        assert isinstance(board, Board)
        assert board.name == "Test Board"
        assert board.owner_id == "test_user"
        assert len(board.columns) == 3  # Default: To Do, In Progress, Done

    def test_add_card(self):
        """Test card creation."""
        kanban = SimpleKanban()
        board = kanban.create_board("test_user", "Test Board")

        card = kanban.add_card("test_user", board.id, "To Do", "Test Card")

        assert isinstance(card, Card)
        assert card.title == "Test Card"
        assert card.column_id in board.columns

    def test_move_card(self):
        """Test card movement between columns."""
        kanban = SimpleKanban()
        board = kanban.create_board("test_user", "Test Board")
        card = kanban.add_card("test_user", board.id, "To Do", "Test Card")

        moved_card = kanban.move_card("test_user", board.id, card.id, "In Progress")

        assert moved_card.id == card.id
        # Find the "In Progress" column
        in_progress_col = next(
            c for c in board.columns.values() if c.name == "In Progress"
        )
        assert moved_card.column_id == in_progress_col.id

    def test_search_cards(self):
        """Test card search functionality."""
        kanban = SimpleKanban()
        board = kanban.create_board("test_user", "Test Board")

        kanban.add_card("test_user", board.id, "To Do", "Important Task")
        kanban.add_card("test_user", board.id, "To Do", "Regular Task")

        # Search by text
        results = kanban.search_cards("test_user", board.id, text="Important")
        assert len(results) == 1
        assert results[0].title == "Important Task"
