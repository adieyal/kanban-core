from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from kanban import AgingCardsView, KanbanFacade, PermissionError, ValidationError
from kanban.models import ColumnPolicy
from kanban.repositories import BoardSnapshot, FrozenMap
from kanban.spi import MoveCardAction
from kanban_adapters import (
    EventBus,
    InMemoryKanbanRepository,
    SynchronousKanbanUnitOfWork,
)


class MutableClock:
    def __init__(self):
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self):
        return self.now


@pytest.mark.parametrize("field", ["created_at", "entered_column_at"])
@pytest.mark.parametrize("value", [datetime(2026, 1, 1), "2026-01-01", 42])
def test_restore_rejects_invalid_lifecycle_timestamps(environment, field, value):
    from kanban import InvalidPersistenceStateError
    from kanban.repositories import restore_board, snapshot_board

    facade, board, _, repository, _ = environment
    card = facade.add_card("owner", board.id, board.columns[0].id, "Task")
    state = restore_board(repository.get(board.id))
    setattr(state.cards[card.id], field, value)
    with pytest.raises(InvalidPersistenceStateError, match="timezone-aware"):
        restore_board(snapshot_board(state))


def test_column_age_measures_elapsed_time_across_dst(environment):
    facade, board, clock, _, _ = environment
    zone = ZoneInfo("America/New_York")
    clock.now = datetime(2026, 11, 1, 0, 30, tzinfo=zone)
    facade.update_column(
        "owner", board.id, board.columns[0].id, policy={"max_age": timedelta(hours=2)}
    )
    card = facade.add_card("owner", board.id, board.columns[0].id, "Before fallback")
    clock.now = datetime(2026, 11, 1, 2, 0, tzinfo=zone)
    assert tuple(item.id for item in facade.aging_cards("owner", board.id).cards) == (
        card.id,
    )


def test_aging_order_distinguishes_repeated_dst_hour(environment):
    facade, board, clock, _, _ = environment
    zone = ZoneInfo("America/New_York")
    facade.update_column(
        "owner", board.id, board.columns[0].id, policy={"max_age": timedelta(minutes=1)}
    )
    # Create the later instant first, so generated IDs/order cannot hide a wall-time tie.
    clock.now = datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=1)
    later = facade.add_card("owner", board.id, board.columns[0].id, "Later")
    clock.now = datetime(2026, 11, 1, 1, 45, tzinfo=zone, fold=0)
    earlier = facade.add_card("owner", board.id, board.columns[0].id, "Earlier")
    clock.now = datetime(2026, 11, 1, 3, 0, tzinfo=zone)
    assert tuple(item.id for item in facade.aging_cards("owner", board.id).cards) == (
        earlier.id,
        later.id,
    )


@pytest.fixture
def environment():
    clock = MutableClock()
    repository = InMemoryKanbanRepository()
    events = EventBus()
    facade = KanbanFacade(
        repository, SynchronousKanbanUnitOfWork(repository, events), clock=clock
    )
    board = facade.create_board("owner", "Queue", ["Waiting", "Working"])
    return facade, board, clock, repository, events


def test_timestamps_follow_lifecycle_and_survive_snapshot(environment):
    facade, board, clock, _, events = environment
    source, destination = board.columns
    card = facade.add_card("owner", board.id, source.id, "First")
    assert card.created_at == card.entered_column_at == clock.now
    created_at = card.created_at
    event = events.get_events()[-1]
    assert event.timestamp == created_at
    assert event.data["after"]["created_at"] == created_at.isoformat()
    clock.now += timedelta(hours=2)
    facade.update_card("owner", board.id, card.id, title="Renamed")
    other = facade.add_card("owner", board.id, source.id, "Second")
    reordered = facade.move_card("owner", board.id, card.id, source.id, position=1)
    assert reordered.entered_column_at == created_at
    assert facade.get_board("owner", board.id).card(other.id).position == 0
    moved = facade.move_card("owner", board.id, card.id, destination.id)
    assert moved.created_at == created_at
    assert moved.entered_column_at == clock.now
    event = events.get_events()[-1]
    assert event.timestamp == clock.now
    assert event.data["entered_column_at"] == clock.now.isoformat()
    restored = facade.get_board("owner", board.id).card(card.id)
    assert restored.created_at == created_at
    assert restored.entered_column_at == clock.now
    version = facade.get_board("owner", board.id).version
    clock.now += timedelta(hours=1)
    assert facade.move_card("owner", board.id, card.id, destination.id) == restored
    assert facade.get_board("owner", board.id).version == version


def test_aging_query_uses_current_column_age_and_excludes_archived(environment):
    facade, board, clock, _, events = environment
    source, destination = board.columns
    facade.update_column(
        "owner", board.id, source.id, policy={"max_age": timedelta(hours=1)}
    )
    facade.update_column(
        "owner",
        board.id,
        destination.id,
        policy=ColumnPolicy(max_age=timedelta(hours=1)),
    )
    oldest = facade.add_card("owner", board.id, source.id, "Oldest")
    archived = facade.add_card("owner", board.id, source.id, "Archived", archived=True)
    moved = facade.add_card("owner", board.id, source.id, "Move me")
    clock.now += timedelta(hours=1)
    assert facade.aging_cards("owner", board.id).cards == ()  # Strict threshold.
    fresh = facade.add_card("owner", board.id, source.id, "Fresh")
    facade.move_card("owner", board.id, moved.id, destination.id)
    clock.now += timedelta(seconds=1)
    before_events = events.get_events()
    version = facade.get_board("owner", board.id).version
    result = facade.aging_cards("owner", board.id)
    assert isinstance(result, AgingCardsView)
    assert tuple(card.id for card in result.cards) == (oldest.id,)
    assert result.unknown_age_cards == ()
    assert {archived.id, moved.id, fresh.id}.isdisjoint(
        card.id for card in result.cards
    )
    assert events.get_events() == before_events
    assert facade.get_board("owner", board.id).version == version
    with pytest.raises(FrozenInstanceError):
        result.cards = ()
    with pytest.raises(FrozenInstanceError):
        result.cards[0].entered_column_at = clock.now
    assert facade.get_board("owner", board.id).column_named(
        "Waiting"
    ).max_age == timedelta(hours=1)


def strip_historical_fields(snapshot):
    # Simulate an actual pre-feature record, including absent column max_age.
    state = dict(snapshot.state)
    cards = []
    for card_id, fields in state["cards"]:
        old_fields = tuple(
            (name, value)
            for name, value in fields
            if name not in {"created_at", "entered_column_at"}
        )
        cards.append((card_id, FrozenMap(old_fields)))
    state["cards"] = FrozenMap(tuple(cards))
    columns = []
    for column_id, fields in state["columns"]:
        column = dict(fields)
        column["policy"] = FrozenMap(
            tuple(
                (name, value) for name, value in column["policy"] if name != "max_age"
            )
        )
        columns.append((column_id, FrozenMap(tuple(column.items()))))
    state["columns"] = FrozenMap(tuple(columns))
    return BoardSnapshot(snapshot.id, snapshot.version, FrozenMap(tuple(state.items())))


def test_historical_unknown_timestamps_remain_unknown(environment):
    facade, board, clock, repository, _ = environment
    source, destination = board.columns
    old = facade.add_card("owner", board.id, source.id, "Historical")
    repository.save(
        strip_historical_fields(repository.get(board.id)), expected_version=2
    )
    restored = facade.get_board("owner", board.id).card(old.id)
    assert restored.created_at is None and restored.entered_column_at is None
    assert facade.aging_cards("owner", board.id).unknown_age_cards == ()
    facade.update_column(
        "owner", board.id, source.id, policy={"max_age": timedelta(days=1)}
    )
    clock.now += timedelta(days=10)
    result = facade.aging_cards("owner", board.id)
    assert result.cards == ()
    assert tuple(card.id for card in result.unknown_age_cards) == (old.id,)
    facade.update_card("owner", board.id, old.id, description="Still unknown")
    assert facade.aging_cards("owner", board.id).unknown_age_cards[0].created_at is None
    moved = facade.move_card("owner", board.id, old.id, destination.id)
    assert moved.created_at is None
    assert moved.entered_column_at == clock.now


@pytest.mark.parametrize("limit", [timedelta(0), timedelta(seconds=-1), 10, "one day"])
def test_invalid_age_limits_fail_atomically(environment, limit):
    facade, board, _, repository, events = environment
    before = repository.get(board.id)
    before_events = events.get_events()
    with pytest.raises(ValidationError, match="positive timedelta"):
        facade.update_column(
            "owner",
            board.id,
            board.columns[0].id,
            name="Changed",
            policy={"max_age": limit},
        )
    assert repository.get(board.id) == before
    assert events.get_events() == before_events
    with pytest.raises(ValidationError, match="positive timedelta"):
        ColumnPolicy(max_age=limit)


def test_naive_clock_and_query_rejected_atomically(environment):
    facade, board, clock, repository, events = environment
    before = repository.get(board.id)
    before_events = events.get_events()
    clock.now = clock.now.replace(tzinfo=None)
    with pytest.raises(ValidationError, match="timezone-aware"):
        facade.add_card("owner", board.id, board.columns[0].id, "Invalid")
    assert repository.get(board.id) == before
    assert events.get_events() == before_events
    with pytest.raises(ValidationError, match="timezone-aware"):
        facade.aging_cards("owner", board.id)
    with pytest.raises(ValidationError, match="timezone-aware"):
        facade.aging_cards("owner", board.id, now=clock.now)
    with pytest.raises(PermissionError):
        facade.aging_cards("outsider", board.id, now=datetime.now(timezone.utc))


def test_automation_sees_timestamps_and_moves_reset_column_age():
    class Runner:
        def __init__(self):
            self.observed = []

        def evaluate(self, event, facts):
            self.observed.append((event, facts))
            if event.type == "card.created":
                target = next(
                    column for column in facts.columns if column.name == "Working"
                )
                return (MoveCardAction(event.entity_id, target.id),)
            return ()

    runner = Runner()
    repository = InMemoryKanbanRepository()
    events = EventBus()
    instant = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def advancing_clock():
        nonlocal instant
        instant += timedelta(seconds=1)
        return instant

    facade = KanbanFacade(
        repository,
        SynchronousKanbanUnitOfWork(repository, events),
        clock=advancing_clock,
        automation_runner=runner,
    )
    board = facade.create_board("owner", "Queue", ["Waiting", "Working"])
    facade.update_column(
        "owner", board.id, board.columns[1].id, policy={"max_age": timedelta(hours=1)}
    )
    card = facade.add_card("owner", board.id, board.columns[0].id, "Task")
    created, moved = events.get_events()[-2:]
    assert created.timestamp == card.created_at
    assert moved.timestamp == card.entered_column_at > card.created_at
    facts = next(
        facts for event, facts in runner.observed if event.type == "card.created"
    )
    assert facts.card(card.id).created_at == created.timestamp
    assert facts.card(card.id).entered_column_at == created.timestamp
    assert facts.columns[1].max_age == timedelta(hours=1)
    final = runner.observed[-1][1].card(card.id)
    assert final.entered_column_at == moved.timestamp


def test_age_sorting_ties_explicit_now_and_clearing_limit(environment):
    facade, board, clock, _, _ = environment
    source = board.columns[0]
    facade.update_column(
        "owner", board.id, source.id, policy={"max_age": timedelta(hours=1)}
    )
    first = facade.add_card("owner", board.id, source.id, "First")
    second = facade.add_card("owner", board.id, source.id, "Second")
    clock.now += timedelta(minutes=1)
    third = facade.add_card("owner", board.id, source.id, "Third")
    facade.move_card("owner", board.id, third.id, source.id, position=0)
    offset_zone = timezone(timedelta(hours=2))
    later = (clock.now + timedelta(hours=2)).astimezone(offset_zone)
    result = facade.aging_cards("owner", board.id, now=later)
    expected = tuple(sorted((first.id, second.id))) + (third.id,)
    assert tuple(card.id for card in result.cards) == expected
    facade.update_column("owner", board.id, source.id, policy={"max_age": None})
    assert facade.aging_cards("owner", board.id, now=later).cards == ()
    assert facade.get_board("owner", board.id).columns[0].max_age is None


def test_rejected_move_preserves_timestamps_and_events(environment):
    facade, board, clock, repository, events = environment
    source, target = board.columns
    card = facade.add_card("owner", board.id, source.id, "Task")
    facade.update_column("owner", board.id, target.id, policy={"wip_limit": 0})
    before = repository.get(board.id)
    before_events = events.get_events()
    clock.now += timedelta(hours=1)
    with pytest.raises(ValidationError, match="WIP limit"):
        facade.move_card("owner", board.id, card.id, target.id)
    assert repository.get(board.id) == before
    assert events.get_events() == before_events
    assert facade.get_board("owner", board.id).card(card.id) == card
