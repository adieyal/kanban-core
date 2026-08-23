from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from kanban import KanbanFacade, NotFoundError, ValidationError
from kanban.spi import (
    AutomationAction,
    AutomationCardFacts,
    AutomationColumnFacts,
    AutomationFacts,
    AutomationRunner,
    MoveCardAction,
)
from kanban_adapters import (
    EventBus,
    InMemoryKanbanRepository,
    SynchronousKanbanUnitOfWork,
)


def make_facade(*, runner: AutomationRunner, workflow_policy=None):
    repository = InMemoryKanbanRepository()
    events = EventBus()
    unit_of_work = SynchronousKanbanUnitOfWork(repository, events)
    return (
        KanbanFacade(
            repository,
            unit_of_work,
            automation_runner=runner,
            workflow_policy=workflow_policy,
        ),
        repository,
        events,
    )


def column_id(facts: AutomationFacts, name: str) -> str:
    return next(column.id for column in facts.columns if column.name == name)


class NoOpRunner:
    def evaluate(self, event, facts: AutomationFacts) -> tuple[AutomationAction, ...]:
        return ()


def test_automation_contract_is_public_and_immutable() -> None:
    facts = AutomationFacts(
        cards=(AutomationCardFacts("card", "todo", "Task", None, False),),
        columns=(AutomationColumnFacts("todo", "To Do"),),
        now=datetime.now(timezone.utc),
    )
    action = MoveCardAction("card", "done")

    with pytest.raises(FrozenInstanceError):
        facts.cards[0].title = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        facts.cards = ()  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        action.card_id = "other"  # type: ignore[misc]
    assert facts.card("card") is not None


def test_runner_move_uses_normal_facade_path() -> None:
    class MoveOnCreate:
        def evaluate(self, event, facts):
            if event.type == "card.created":
                return (
                    MoveCardAction(event.entity_id, column_id(facts, "In Progress")),
                )
            return ()

    facade, repository, _ = make_facade(runner=MoveOnCreate())
    board = facade.create_board("alice", "Launch")
    todo = board.column_named("To Do")
    in_progress = board.column_named("In Progress")
    assert todo is not None and in_progress is not None

    card = facade.add_card("alice", board.id, todo.id, "Task")

    assert card.column_id == in_progress.id
    assert facade.get_board("alice", board.id).card(card.id).column_id == in_progress.id
    assert repository.get(board.id) is not None


def test_automation_move_obeys_wip_policy() -> None:
    class MoveOnCreate:
        def evaluate(self, event, facts):
            return (
                (MoveCardAction(event.entity_id, column_id(facts, "In Progress")),)
                if event.type == "card.created"
                else ()
            )

    facade, repository, _ = make_facade(runner=MoveOnCreate())
    board = facade.create_board("alice", "Launch")
    todo = board.column_named("To Do")
    in_progress = board.column_named("In Progress")
    assert todo is not None and in_progress is not None

    facade.update_column("alice", board.id, in_progress.id, policy={"wip_limit": 0})
    with pytest.raises(ValidationError, match="WIP limit"):
        facade.add_card("alice", board.id, todo.id, "Task")
    stored = facade.get_board("alice", board.id)
    assert stored.cards == ()
    assert repository.get(board.id).version == 2


def test_automation_move_obeys_workflow_policy() -> None:
    class MoveOnCreate:
        def evaluate(self, event, facts):
            return (
                (MoveCardAction(event.entity_id, column_id(facts, "In Progress")),)
                if event.type == "card.created"
                else ()
            )

    class RejectMoves:
        def validate_move(self, context):
            raise ValidationError("workflow rejected")

        def validate_create(self, context):
            pass

        def validate_update(self, context):
            pass

        def validate_delete(self, context):
            pass

    facade, _, _ = make_facade(runner=MoveOnCreate(), workflow_policy=RejectMoves())
    board = facade.create_board("alice", "Launch")
    todo = board.column_named("To Do")
    assert todo is not None

    with pytest.raises(ValidationError, match="workflow rejected"):
        facade.add_card("alice", board.id, todo.id, "Task")
    assert facade.get_board("alice", board.id).cards == ()


def test_invalid_automation_reference_is_transactional() -> None:
    class InvalidRunner:
        def evaluate(self, event, facts):
            return (
                (MoveCardAction(event.entity_id, "missing"),)
                if event.type == "card.created"
                else ()
            )

    facade, _, _ = make_facade(runner=InvalidRunner())
    board = facade.create_board("alice", "Launch")
    todo = board.column_named("To Do")
    assert todo is not None

    with pytest.raises(NotFoundError, match="Target column"):
        facade.add_card("alice", board.id, todo.id, "Task")
    assert facade.get_board("alice", board.id).cards == ()


def test_automation_chain_preserves_correlation_and_causation() -> None:
    class ChainRunner:
        def evaluate(self, event, facts):
            if event.type == "card.created":
                return (
                    MoveCardAction(event.entity_id, column_id(facts, "In Progress")),
                )
            if event.type == "card.moved" and event.data["to_column_id"] == column_id(
                facts, "In Progress"
            ):
                return (MoveCardAction(event.entity_id, column_id(facts, "Done")),)
            return ()

    facade, _, events = make_facade(runner=ChainRunner())
    board = facade.create_board("alice", "Launch")
    todo = board.column_named("To Do")
    assert todo is not None
    card = facade.add_card("alice", board.id, todo.id, "Task")

    moved = [event for event in events.get_events() if event.type == "card.moved"]
    assert len(moved) == 2
    assert moved[0].correlation_id == moved[1].correlation_id
    assert moved[1].causation_id == moved[0].id
    done = board.column_named("Done")
    assert done is not None
    assert facade.get_board("alice", board.id).card(card.id).column_id == done.id


def test_chain_limit_prevents_recursive_automation_commit() -> None:
    class LoopRunner:
        def evaluate(self, event, facts):
            if event.type == "card.created":
                return (
                    MoveCardAction(event.entity_id, column_id(facts, "In Progress")),
                )
            if event.type == "card.moved":
                target_name = (
                    "Done"
                    if event.data["to_column_id"] == column_id(facts, "In Progress")
                    else "In Progress"
                )
                target = column_id(facts, target_name)
                return (MoveCardAction(event.entity_id, target),)
            return ()

    facade, _, _ = make_facade(runner=LoopRunner())
    board = facade.create_board("alice", "Launch")
    todo = board.column_named("To Do")
    assert todo is not None

    with pytest.raises(ValidationError, match="chain limit"):
        facade.add_card("alice", board.id, todo.id, "Task")
    assert facade.get_board("alice", board.id).cards == ()


def test_noop_runner_does_not_add_a_persistence_write() -> None:
    class CountingRepository(InMemoryKanbanRepository):
        def __init__(self):
            super().__init__()
            self.saves = 0

        def save(self, board, expected_version=None):
            self.saves += 1
            return super().save(board, expected_version)

    repository = CountingRepository()
    events = EventBus()
    facade = KanbanFacade(
        repository,
        SynchronousKanbanUnitOfWork(repository, events),
        automation_runner=NoOpRunner(),
    )
    board = facade.create_board("alice", "Launch")
    todo = board.column_named("To Do")
    assert todo is not None
    before = repository.saves

    facade.add_card("alice", board.id, todo.id, "Task")

    assert repository.saves == before + 1
