from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone

import pytest

from kanban import (
    ConcurrencyError,
    KanbanFacade,
    ValidationError,
)
from kanban.automation import create_auto_move_rule
from kanban.models import Board, CustomField, FieldType
from kanban.spi import CardMovePolicyContext, CardPolicyContext
from kanban.spi import Event as DomainEvent
from kanban_adapters import (
    EventBus,
    InMemoryKanbanRepository,
    SynchronousKanbanUnitOfWork,
)


class RecordingPolicy:
    def __init__(self) -> None:
        self.created: list[CardPolicyContext] = []
        self.updated: list[CardPolicyContext] = []
        self.moved: list[CardMovePolicyContext] = []
        self.deleted: list[CardPolicyContext] = []

    def validate_create(self, context: CardPolicyContext) -> None:
        self.created.append(context)
        if context.title == "forbidden":
            raise ValidationError("Rejected by workflow policy")

    def validate_update(self, context: CardPolicyContext) -> None:
        self.updated.append(context)

    def validate_move(self, context: CardMovePolicyContext) -> None:
        self.moved.append(context)

    def validate_delete(self, context: CardPolicyContext) -> None:
        self.deleted.append(context)


class RecordingUnitOfWork:
    def __init__(
        self, repository: InMemoryKanbanRepository, publisher: EventBus
    ) -> None:
        self.repository = repository
        self.publisher = publisher
        self.save_calls: list[tuple[tuple[DomainEvent, ...], int | None]] = []

    def save(
        self,
        board: Board,
        events: tuple[DomainEvent, ...],
        expected_version: int | None = None,
    ) -> Board:
        self.save_calls.append((events, expected_version))
        saved = self.repository.save(board, expected_version)
        for event in events:
            self.publisher.publish(replace(event, aggregate_version=saved.version))
        return saved

    def delete(
        self,
        board_id: str,
        events: tuple[DomainEvent, ...],
        expected_version: int,
    ) -> None:
        self.repository.delete(board_id, expected_version=expected_version)
        for event in events:
            self.publisher.publish(replace(event, aggregate_version=expected_version))

    def emit(self, events: tuple[DomainEvent, ...], aggregate_version: int) -> None:
        for event in events:
            self.publisher.publish(replace(event, aggregate_version=aggregate_version))


def test_workflow_policy_receives_detached_context_and_can_reject() -> None:
    repository = InMemoryKanbanRepository()
    publisher = EventBus()
    policy = RecordingPolicy()
    facade = KanbanFacade(
        repository,
        SynchronousKanbanUnitOfWork(repository, publisher),
        workflow_policy=policy,
    )
    board = facade.create_board("owner", "Board", ["A"])

    with pytest.raises(ValidationError, match="Rejected by workflow policy"):
        facade.add_card("owner", board.id, board.columns[0].id, "forbidden")

    assert policy.created[0].board_id == board.id
    with pytest.raises(FrozenInstanceError):
        policy.created[0].title = "changed"
    assert repository.get(board.id).cards == {}


def test_workflow_policy_observes_all_card_lifecycle_operations() -> None:
    repository = InMemoryKanbanRepository()
    publisher = EventBus()
    policy = RecordingPolicy()
    facade = KanbanFacade(
        repository,
        SynchronousKanbanUnitOfWork(repository, publisher),
        workflow_policy=policy,
    )
    board = facade.create_board("owner", "Board", ["A", "B"])
    card = facade.add_card("owner", board.id, board.columns[0].id, "Card")

    facade.update_card("owner", board.id, card.id, description="updated")
    facade.move_card("owner", board.id, card.id, board.columns[1].id)
    facade.delete_card("owner", board.id, card.id)

    assert len(policy.created) == 1
    assert len(policy.updated) == 1
    assert policy.moved[0].from_column_id == board.columns[0].id
    assert policy.moved[0].to_column_id == board.columns[1].id
    assert len(policy.deleted) == 1


def test_injected_unit_of_work_owns_state_and_event_commit() -> None:
    repository = InMemoryKanbanRepository()
    publisher = EventBus()
    unit_of_work = RecordingUnitOfWork(repository, publisher)
    facade = KanbanFacade(repository, unit_of_work)

    board = facade.create_board("owner", "Board", ["A"])
    facade.add_card("owner", board.id, board.columns[0].id, "Card")

    assert len(unit_of_work.save_calls) == 2
    assert unit_of_work.save_calls[1][1] == board.version
    assert publisher.get_events()[-1].aggregate_version == 2


def test_event_envelope_tracks_schema_correlation_causation_and_version() -> None:
    repository = InMemoryKanbanRepository()
    publisher = EventBus()
    facade = KanbanFacade(
        repository, SynchronousKanbanUnitOfWork(repository, publisher)
    )
    board = facade.create_board("owner", "Board", ["To Do", "Doing"])
    card = facade.add_card("owner", board.id, board.columns[0].id, "Card")
    stored = repository.get(board.id)
    assert stored is not None
    stored.custom_fields["labels"] = CustomField("Labels", FieldType.MULTISELECT)
    stored.automation_rules.append(create_auto_move_rule("ready", "Doing"))
    repository.save(stored, expected_version=stored.version)

    facade.update_card("owner", board.id, card.id, custom_fields={"labels": {"ready"}})

    parent, child = publisher.get_events()[-2:]
    assert parent.schema_version == 1
    assert parent.correlation_id == parent.id
    assert parent.causation_id is None
    assert child.correlation_id == parent.id
    assert child.causation_id == parent.id
    assert parent.aggregate_version == child.aggregate_version == 4
    assert parent.to_dict()["schema_version"] == 1


def test_manual_event_envelope_fields_remain_backward_compatible() -> None:
    event = DomainEvent(
        type="example",
        entity_id="one",
        entity_type="example",
        id="event-one",
        timestamp=datetime.now(timezone.utc),
    )

    assert event.schema_version == 1
    assert event.correlation_id is None
    assert event.aggregate_version is None


def test_synchronous_unit_of_work_rejects_stale_delete_without_emitting() -> None:
    repository = InMemoryKanbanRepository()
    publisher = EventBus()
    unit_of_work = SynchronousKanbanUnitOfWork(repository, publisher)
    board = repository.save(Board(id="board", name="Board"))
    board.name = "Updated"
    repository.save(board, expected_version=1)
    event = DomainEvent(
        type="board.deleted",
        entity_id="board",
        entity_type="board",
        id="event-delete",
        timestamp=datetime.now(timezone.utc),
    )

    with pytest.raises(ConcurrencyError, match="Expected v1, found v2"):
        unit_of_work.delete("board", (event,), expected_version=1)

    assert repository.exists("board")
    assert publisher.get_events() == []
