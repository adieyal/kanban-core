"""Tests for repository implementations."""

import pytest

from kanban import Board, ConcurrencyError, InMemoryKanbanRepository


class TestInMemoryKanbanRepository:
    """Test in-memory repository implementation."""

    def test_save_and_get(self):
        """Test saving and retrieving boards."""
        repo = InMemoryKanbanRepository()
        board = Board(id="board1", name="Test Board")

        # Save board
        saved_board = repo.save(board)
        assert saved_board.version == 1

        # Retrieve board
        retrieved = repo.get("board1")
        assert retrieved is not None
        assert retrieved.id == "board1"
        assert retrieved.name == "Test Board"
        assert retrieved.version == 1

    def test_get_nonexistent(self):
        """Test getting non-existent board."""
        repo = InMemoryKanbanRepository()
        assert repo.get("nonexistent") is None

    def test_optimistic_locking(self):
        """Test optimistic concurrency control."""
        repo = InMemoryKanbanRepository()
        board = Board(id="board1", name="Test Board")

        # Save initial version
        saved = repo.save(board)
        assert saved.version == 1

        # Update with correct version
        saved.name = "Updated Board"
        updated = repo.save(saved, expected_version=1)
        assert updated.version == 2

        # Try to update with old version - should fail
        old_board = Board(id="board1", name="Old Update", version=1)
        with pytest.raises(ConcurrencyError, match="Expected v1, found v2"):
            repo.save(old_board, expected_version=1)

    def test_save_without_version_check(self):
        """Test saving without version checking."""
        repo = InMemoryKanbanRepository()
        board = Board(id="board1", name="Test Board")

        # Save without version check
        saved = repo.save(board)
        assert saved.version == 1

        # Save again without version check (should work)
        saved.name = "Updated"
        updated = repo.save(saved)
        assert updated.version == 2

    def test_delete(self):
        """Test board deletion."""
        repo = InMemoryKanbanRepository()
        board = Board(id="board1", name="Test Board")

        # Save and verify exists
        repo.save(board)
        assert repo.exists("board1")

        # Delete and verify doesn't exist
        repo.delete("board1")
        assert not repo.exists("board1")
        assert repo.get("board1") is None

        # Delete non-existent (should not raise error)
        repo.delete("nonexistent")

    def test_list_all(self):
        """Test listing all boards."""
        repo = InMemoryKanbanRepository()

        # Empty initially
        assert repo.list_all() == []

        # Add some boards
        board1 = Board(id="board1", name="Board 1")
        board2 = Board(id="board2", name="Board 2")
        repo.save(board1)
        repo.save(board2)

        # Should return both
        all_boards = repo.list_all()
        assert len(all_boards) == 2
        board_ids = {board.id for board in all_boards}
        assert board_ids == {"board1", "board2"}

    def test_exists(self):
        """Test checking if board exists."""
        repo = InMemoryKanbanRepository()
        
        assert not repo.exists("board1")
        
        board = Board(id="board1", name="Test Board")
        repo.save(board)
        
        assert repo.exists("board1")
        assert not repo.exists("board2")

    def test_thread_safety(self):
        """Test that operations are thread-safe."""
        import threading
        import time

        repo = InMemoryKanbanRepository()
        board = Board(id="board1", name="Test Board")
        repo.save(board)

        results = []
        errors = []

        def update_board(thread_id):
            try:
                # Get current board
                current = repo.get("board1")
                current.name = f"Updated by thread {thread_id}"
                time.sleep(0.01)  # Small delay to increase chance of race condition
                updated = repo.save(current, expected_version=current.version)
                results.append(updated.version)
            except Exception as e:
                errors.append(e)

        # Run multiple threads updating the same board
        threads = []
        for i in range(5):
            t = threading.Thread(target=update_board, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Some updates should succeed, some might fail due to concurrency
        assert len(results) + len(errors) == 5
        assert len(results) >= 1  # At least one should succeed