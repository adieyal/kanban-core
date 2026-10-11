from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from kanban import (
    AgingCardDetailsView,
    BoardImport,
    CardAgeView,
    CardImport,
    ColumnImport,
    KanbanFacade,
    PermissionError,
    ValidationError,
)
from kanban_adapters import (
    EventBus,
    InMemoryKanbanRepository,
    SynchronousKanbanUnitOfWork,
)


def environment(entered_at):
    repo = InMemoryKanbanRepository()
    events = EventBus()
    facade = KanbanFacade(repo, SynchronousKanbanUnitOfWork(repo, events))
    board = facade.import_board(
        "owner",
        BoardImport(
            "queue",
            "Queue",
            "owner",
            (
                ColumnImport("review", "Review", max_age=timedelta(hours=1)),
                ColumnImport("unlimited", "Unlimited"),
            ),
            (
                CardImport("known", "review", "Known", entered_column_at=entered_at),
                CardImport("unknown", "review", "Unknown"),
                CardImport(
                    "archived",
                    "review",
                    "Archived",
                    archived=True,
                    entered_column_at=entered_at,
                ),
                CardImport(
                    "unlimited",
                    "unlimited",
                    "Unmonitored",
                    entered_column_at=entered_at,
                ),
            ),
        ),
    )
    return facade, board, repo, events


def test_details_include_column_elapsed_age_and_separate_unknown_history():
    entered = datetime(2026, 1, 1, tzinfo=timezone.utc)
    now = entered + timedelta(hours=2)
    facade, board, repo, events = environment(entered)
    before = repo.get(board.id)
    before_events = events.get_events()
    result = facade.aging_card_details("owner", board.id, now)
    assert isinstance(result, AgingCardDetailsView) and result.evaluated_at == now
    assert len(result.cards) == len(result.unknown_age_cards) == 1
    row = result.cards[0]
    assert isinstance(row, CardAgeView)
    assert row.card.id == "known" and row.column.name == "Review"
    assert row.column.id == row.card.column_id
    assert row.age == timedelta(hours=2)
    assert result.unknown_age_cards[0].card.id == "unknown"
    assert result.unknown_age_cards[0].age is None
    assert repo.get(board.id) == before and events.get_events() == before_events
    with pytest.raises(FrozenInstanceError):
        row.age = timedelta(0)
    legacy = facade.aging_cards("owner", board.id, now)
    assert legacy.cards == tuple(item.card for item in result.cards)
    assert legacy.unknown_age_cards == tuple(
        item.card for item in result.unknown_age_cards
    )


def test_details_capture_one_clock_instant_and_remain_detached():
    entered = datetime(2026, 1, 1, tzinfo=timezone.utc)
    facade, board, _, _ = environment(entered)
    calls = []

    def clock():
        calls.append(True)
        return entered + timedelta(hours=2, seconds=len(calls))

    facade._core.clock = clock
    result = facade.aging_card_details("owner", board.id)
    assert len(calls) == 1 and result.cards[0].age == timedelta(hours=2, seconds=1)
    facade.update_column("owner", board.id, "review", name="Renamed")
    assert result.cards[0].column.name == "Review"


def test_details_measure_actual_elapsed_time_across_dst():
    zone = ZoneInfo("America/New_York")
    entered = datetime(2026, 11, 1, 0, 30, tzinfo=zone)
    facade, board, _, _ = environment(entered)
    result = facade.aging_card_details(
        "owner", board.id, datetime(2026, 11, 1, 2, 0, tzinfo=zone)
    )
    assert result.cards[0].age == timedelta(hours=2, minutes=30)


def test_details_enforce_permissions_timezone_and_strict_threshold():
    entered = datetime(2026, 1, 1, tzinfo=timezone.utc)
    facade, board, _, _ = environment(entered)
    assert (
        facade.aging_card_details("owner", board.id, entered + timedelta(hours=1)).cards
        == ()
    )
    with pytest.raises(PermissionError):
        facade.aging_card_details("stranger", board.id)
    with pytest.raises(ValidationError):
        facade.aging_card_details("owner", board.id, datetime(2026, 1, 1))
