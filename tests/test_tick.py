from datetime import datetime, timezone

import pytest

from kanban import KanbanFacade, PermissionError, ValidationError
from kanban.spi import MoveCardAction
from kanban_adapters import (
    EventBus,
    InMemoryKanbanRepository,
    SynchronousKanbanUnitOfWork,
)


class TickMoves:
    def evaluate(self, event, facts):
        if event.type != "board.tick":
            return ()
        target = next(col.id for col in facts.columns if col.name == "Done")
        return tuple(
            MoveCardAction(card.id, target)
            for card in facts.cards
            if card.column_id != target
        )


def setup(runner=None, count=0):
    repo = InMemoryKanbanRepository()
    events = EventBus()
    facade = KanbanFacade(
        repo,
        SynchronousKanbanUnitOfWork(repo, events),
        automation_runner=runner,
        clock=lambda: datetime(2026, 10, 11, tzinfo=timezone.utc),
    )
    board = facade.create_board("alice", "Queue")
    for index in range(count):
        facade.add_card("alice", board.id, board.columns[0].id, f"Task {index}")
    return facade, repo, events, facade.get_board("alice", board.id)


def test_tick_batches_busy_board_and_repeated_ticks_converge():
    facade, repo, events, board = setup(TickMoves(), count=50)
    result = facade.tick("alice", board.id, max_actions=30)
    assert len(result.processed_card_ids) == 30
    assert len(result.deferred_card_ids) == 20
    assert len(set(result.processed_card_ids + result.deferred_card_ids)) == 50
    stored = facade.get_board("alice", board.id)
    assert sum(card.column_id == board.columns[-1].id for card in stored.cards) == 30
    moved = [event for event in events.get_events() if event.type == "card.moved"]
    tick = next(event for event in events.get_events() if event.type == "board.tick")
    assert all(event.causation_id == tick.id for event in moved)
    assert all(event.correlation_id == tick.id for event in moved)
    assert repo.get(board.id).version == board.version + 1
    result = facade.tick("alice", board.id, max_actions=30)
    assert len(result.processed_card_ids) == 20
    assert result.deferred_card_ids == ()
    before = repo.get(board.id)
    assert facade.tick("alice", board.id).processed_card_ids == ()
    assert repo.get(board.id) == before


def test_tick_without_automation_emits_one_event_without_state_write():
    facade, repo, events, board = setup()
    before = repo.get(board.id)
    assert facade.tick("alice", board.id).processed_card_ids == ()
    assert repo.get(board.id) == before
    assert events.get_events()[-1].type == "board.tick"


def test_tick_invalid_selected_action_is_atomic():
    facade, repo, events, board = setup(TickMoves(), count=3)
    facade.update_column(
        "alice", board.id, board.columns[-1].id, policy={"wip_limit": 1}
    )
    before = repo.get(board.id)
    before_events = events.get_events()
    with pytest.raises(ValidationError, match="WIP"):
        facade.tick("alice", board.id)
    assert repo.get(board.id) == before
    assert events.get_events() == before_events


def test_tick_cycle_still_fails_atomically():
    class Loop(TickMoves):
        def evaluate(self, event, facts):
            if event.type == "board.tick":
                return super().evaluate(event, facts)
            if event.type == "card.moved":
                target = next(
                    col.id
                    for col in facts.columns
                    if col.id != event.data["to_column_id"]
                )
                return (MoveCardAction(event.entity_id, target),)
            return ()

    facade, repo, events, board = setup(Loop(), count=1)
    before = repo.get(board.id)
    before_events = events.get_events()
    with pytest.raises(ValidationError, match="chain limit"):
        facade.tick("alice", board.id)
    assert repo.get(board.id) == before
    assert events.get_events() == before_events


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, None])
def test_tick_rejects_invalid_batch_limits(limit):
    facade, _, _, board = setup()
    with pytest.raises(ValidationError, match="positive integer"):
        facade.tick("alice", board.id, max_actions=limit)


def test_tick_requires_manage_automation_permission():
    facade, _, _, board = setup()
    facade.update_board("alice", board.id, team_ids={"alice", "bob"})
    with pytest.raises(PermissionError):
        facade.tick("bob", board.id)


def test_tick_facts_use_trigger_time_with_an_advancing_clock():
    class RecordTime(TickMoves):
        observations = []

        def evaluate(self, event, facts):
            if event.type in {"board.tick", "card.moved"}:
                self.observations.append((event, facts.now))
            return super().evaluate(event, facts)

    runner = RecordTime()
    facade, _, _, board = setup(runner, count=2)
    from datetime import timedelta

    times = iter(
        datetime(2026, 10, 11, tzinfo=timezone.utc) + timedelta(seconds=i)
        for i in range(100)
    )
    facade._core.clock = lambda: next(times)
    facade._core.event_factory.clock = facade._core.clock
    facade.tick("alice", board.id)
    tick_event = runner.observations[0][0]
    assert all(now == tick_event.timestamp for _, now in runner.observations)
