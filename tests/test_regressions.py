from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

import kanban
from kanban import ConcurrencyError, KanbanFacade, ValidationError
from kanban.automation import create_auto_move_rule
from kanban.events import Event
from kanban.models import CustomField, FieldType
from kanban.permissions import Permission, SimplePermissionPolicy
from kanban_adapters import (
    EventBus,
    InMemoryKanbanRepository,
    SynchronousKanbanUnitOfWork,
)


class MutableClock:
    def __init__(self, now: datetime):
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def make_facade(**kwargs):
    repository = kwargs.pop("repository", InMemoryKanbanRepository())
    event_bus = kwargs.pop("event_publisher", EventBus())
    unit_of_work = kwargs.pop(
        "unit_of_work", SynchronousKanbanUnitOfWork(repository, event_bus)
    )
    facade = KanbanFacade(repository, unit_of_work, **kwargs)
    return facade, repository, event_bus


def test_public_namespace_is_the_facade_contract_only():
    assert set(kanban.__all__) == {
        "BoardView",
        "CardView",
        "ColumnView",
        "ConcurrencyError",
        "KanbanError",
        "KanbanFacade",
        "NotFoundError",
        "PermissionError",
        "ValidationError",
    }


def test_facade_returns_immutable_detached_views():
    facade, repository, _ = make_facade()
    board = facade.create_board("owner", "Board", ["A"])
    column = board.columns[0]
    card = facade.add_card("owner", board.id, column.id, "Card", custom_fields={})

    with pytest.raises(FrozenInstanceError):
        card.title = "Changed"
    with pytest.raises(TypeError):
        card.custom_fields["new"] = "value"
    assert repository.get(board.id).cards[card.id].title == "Card"


def test_entry_criteria_receives_the_real_candidate_card():
    facade, _, _ = make_facade()
    board = facade.create_board("owner", "Board", ["A"])
    column = board.columns[0]
    facade.update_column(
        "owner",
        board.id,
        column.id,
        policy={"entry_criteria": lambda card: card.title == "Ready"},
    )

    created = facade.add_card("owner", board.id, column.id, "Ready")

    assert created.title == "Ready"


def test_failed_save_does_not_publish_events_or_leak_mutations():
    class FailingRepository(InMemoryKanbanRepository):
        fail = False

        def save(self, board, expected_version=None):
            if self.fail:
                raise ConcurrencyError("simulated conflict")
            return super().save(board, expected_version)

    repository = FailingRepository()
    facade, _, event_bus = make_facade(repository=repository)
    board = facade.create_board("owner", "Before")
    events_before = event_bus.get_events()
    repository.fail = True

    with pytest.raises(ConcurrencyError):
        facade.update_board("owner", board.id, name="After")

    assert event_bus.get_events() == events_before
    assert repository.get(board.id).name == "Before"


def test_move_tracks_time_and_reindexes_both_columns():
    clock = MutableClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    facade, repository, _ = make_facade(clock=clock)
    board = facade.create_board("owner", "Board", ["A", "B"])
    first_column, second_column = board.columns
    first = facade.add_card("owner", board.id, first_column.id, "First")
    second = facade.add_card("owner", board.id, first_column.id, "Second")
    clock.now += timedelta(hours=2)

    moved = facade.move_card("owner", board.id, first.id, second_column.id, position=0)
    persisted = repository.get(board.id)

    assert persisted.cards[moved.id].time_in_column[first_column.id] == timedelta(
        hours=2
    )
    assert persisted.columns[first_column.id].card_ids == [second.id]
    assert persisted.cards[second.id].position == 0
    assert persisted.columns[second_column.id].card_ids == [first.id]
    assert persisted.cards[first.id].position == 0


def test_delete_card_cleans_dependency_references():
    facade, repository, _ = make_facade()
    board = facade.create_board("owner", "Board", ["A"])
    column = board.columns[0]
    blocker = facade.add_card("owner", board.id, column.id, "Blocker")
    blocked = facade.add_card("owner", board.id, column.id, "Blocked")
    facade.block_card("owner", board.id, blocked.id, blocker.id)

    facade.delete_card("owner", board.id, blocker.id)

    persisted = repository.get(board.id)
    assert persisted.cards[blocked.id].blocked_by == set()


def test_empty_member_permission_set_is_respected():
    checker = SimplePermissionPolicy(set())
    facade, repository, _ = make_facade(permission_checker=checker)
    board = facade.create_board("owner", "Board")
    stored = repository.get(board.id)
    stored.team_ids.add("member")

    assert not checker.has_permission("member", stored, Permission.VIEW_BOARD)


def test_search_accepts_a_list_of_assignee_ids():
    facade, _, _ = make_facade()
    board = facade.create_board("owner", "Board", ["A"])
    column = board.columns[0]
    facade.add_card("owner", board.id, column.id, "Assigned", assignee_ids={"alice"})

    results = facade.search_cards("owner", board.id, assignee_ids=["alice"])

    assert [card.title for card in results] == ["Assigned"]


def test_event_handlers_cannot_rewrite_history_or_each_other():
    bus = EventBus()
    observed = []

    def mutating_handler(event):
        event.data["nested"]["value"] = "mutated"

    def observing_handler(event):
        observed.append(event.data["nested"]["value"])

    bus.subscribe("example", mutating_handler)
    bus.subscribe("example", observing_handler)
    event = Event(
        "example",
        "entity",
        "example",
        "event",
        datetime.now(timezone.utc),
        {"nested": {"value": "original"}},
    )

    bus.publish(event)

    assert observed == ["original"]
    assert bus.get_events()[0].data["nested"]["value"] == "original"


def test_unknown_card_fields_are_rejected():
    facade, _, _ = make_facade()
    board = facade.create_board("owner", "Board", ["A"])
    card = facade.add_card("owner", board.id, board.columns[0].id, "Card")

    with pytest.raises(ValidationError, match="titel"):
        facade.update_card("owner", board.id, card.id, titel="typo")


def test_auto_move_runs_end_to_end_and_publishes_after_commit():
    facade, repository, event_bus = make_facade()
    board = facade.create_board("owner", "Board", ["To Do", "Doing"])
    todo, doing = board.columns
    card = facade.add_card("owner", board.id, todo.id, "Card")
    stored = repository.get(board.id)
    stored.custom_fields["labels"] = CustomField("Labels", FieldType.MULTISELECT)
    stored.automation_rules.append(create_auto_move_rule("ready", "Doing"))
    repository.save(stored, expected_version=stored.version)

    facade.update_card("owner", board.id, card.id, custom_fields={"labels": {"ready"}})

    persisted = repository.get(board.id)
    assert persisted.cards[card.id].column_id == doing.id
    assert [event.type for event in event_bus.get_events()][-2:] == [
        "card.updated",
        "card.moved",
    ]
    assert event_bus.get_events()[-1].user_id == "owner"
