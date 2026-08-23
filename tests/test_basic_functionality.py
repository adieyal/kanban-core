"""Public-facade smoke tests."""

from kanban import BoardView, CardView, KanbanFacade
from kanban_adapters import (
    EventBus,
    InMemoryKanbanRepository,
    SynchronousKanbanUnitOfWork,
)


def make_kanban() -> KanbanFacade:
    repository = InMemoryKanbanRepository()
    return KanbanFacade(repository, SynchronousKanbanUnitOfWork(repository, EventBus()))


class TestBasicFunctionality:
    def test_create_board(self):
        kanban = make_kanban()

        board = kanban.create_board("test_user", "Test Board")

        assert isinstance(board, BoardView)
        assert board.name == "Test Board"
        assert board.owner_id == "test_user"
        assert len(board.columns) == 3

    def test_add_card(self):
        kanban = make_kanban()
        board = kanban.create_board("test_user", "Test Board")
        todo = board.column_named("To Do")
        assert todo is not None

        card = kanban.add_card("test_user", board.id, todo.id, "Test Card")

        assert isinstance(card, CardView)
        assert card.title == "Test Card"
        assert card.column_id == todo.id

    def test_move_card(self):
        kanban = make_kanban()
        board = kanban.create_board("test_user", "Test Board")
        todo = board.column_named("To Do")
        in_progress = board.column_named("In Progress")
        assert todo is not None and in_progress is not None
        card = kanban.add_card("test_user", board.id, todo.id, "Test Card")

        moved_card = kanban.move_card("test_user", board.id, card.id, in_progress.id)

        assert moved_card.id == card.id
        assert moved_card.column_id == in_progress.id

    def test_search_cards(self):
        kanban = make_kanban()
        board = kanban.create_board("test_user", "Test Board")
        todo = board.column_named("To Do")
        assert todo is not None
        kanban.add_card("test_user", board.id, todo.id, "Important Task")
        kanban.add_card("test_user", board.id, todo.id, "Regular Task")

        results = kanban.search_cards("test_user", board.id, text="Important")

        assert len(results) == 1
        assert results[0].title == "Important Task"
