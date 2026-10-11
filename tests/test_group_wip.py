from dataclasses import FrozenInstanceError, replace

import pytest

from kanban import KanbanFacade, ValidationError, WipGroup
from kanban.models import Board, Card, Column
from kanban.repositories import FrozenMap, restore_board, snapshot_board
from kanban.spi import ConcurrencyError, InvalidPersistenceStateError
from kanban_adapters import (
    EventBus,
    InMemoryKanbanRepository,
    SynchronousKanbanUnitOfWork,
)


def test_group_enforces_create_move_and_internal_movement(kanban):
    board = kanban.create_board("owner", "Board", ["Todo", "Doing", "Review", "Done"])
    todo, doing, review, done = [column.id for column in board.columns]
    group = WipGroup("Active", [doing, review], 1)
    updated = kanban.update_board("owner", board.id, wip_groups=[group])
    assert updated.wip_groups == (group,)
    active = kanban.add_card("owner", board.id, doing, "Active", archived=True)
    pending = kanban.add_card("owner", board.id, todo, "Pending")
    with pytest.raises(ValidationError, match="Active"):
        kanban.add_card("owner", board.id, review, "Another")
    with pytest.raises(ValidationError, match="Active"):
        kanban.move_card("owner", board.id, pending.id, review)
    kanban.move_card("owner", board.id, active.id, review)
    kanban.move_card("owner", board.id, active.id, done)
    kanban.move_card("owner", board.id, pending.id, doing)


def test_overlapping_groups_all_enforce(kanban):
    board = kanban.create_board("owner", "Board", ["A", "B", "C", "Outside"])
    a, b, c, outside = [col.id for col in board.columns]
    kanban.update_board(
        "owner",
        board.id,
        wip_groups=[WipGroup("AB", (a, b), 2), WipGroup("BC", (b, c), 1)],
    )
    kanban.add_card("owner", board.id, c, "C occupant")
    card = kanban.add_card("owner", board.id, a, "A occupant")
    with pytest.raises(ValidationError, match="BC"):
        kanban.move_card("owner", board.id, card.id, b)
    kanban.move_card("owner", board.id, card.id, outside)


@pytest.mark.parametrize(
    "args",
    [
        ("", ("x",), 1),
        ("A", (), 1),
        ("A", ("x", "x"), 1),
        ("A", ("",), 1),
        ("A", ("x",), 0),
        ("A", ("x",), -1),
        ("A", ("x",), True),
        ("A", ("x",), 1.5),
    ],
)
def test_invalid_group(args):
    with pytest.raises(ValidationError):
        WipGroup(*args)


def test_configuration_is_immutable_validated_and_removable(kanban):
    board = kanban.create_board("owner", "Board")
    column = board.columns[0].id
    members = [column]
    group = WipGroup("Group", members, 2)
    members.clear()
    assert group.column_ids == (column,)
    with pytest.raises(FrozenInstanceError):
        group.limit = 4
    with pytest.raises(ValidationError, match="unknown"):
        kanban.update_board(
            "owner", board.id, wip_groups=[WipGroup("Unknown", ("missing",), 1)]
        )
    with pytest.raises(ValidationError, match="distinct"):
        kanban.update_board("owner", board.id, wip_groups=[group, group])
    kanban.update_board("owner", board.id, wip_groups=[group])
    with pytest.raises(ValidationError, match="referenced"):
        kanban.delete_column("owner", board.id, column)
    kanban.update_board("owner", board.id, wip_groups=[])
    kanban.delete_column("owner", board.id, column)


def test_old_snapshot_and_invalid_restored_group():
    board = Board(
        "board", owner_id="owner", columns={"column": Column("column", "board")}
    )
    snapshot = snapshot_board(board)
    historic = replace(
        snapshot,
        state=FrozenMap(
            tuple((key, value) for key, value in snapshot.state if key != "wip_groups")
        ),
    )
    assert restore_board(historic).wip_groups == ()
    board.wip_groups = (WipGroup("Unknown", ("missing",), 1),)
    with pytest.raises(InvalidPersistenceStateError, match="WIP"):
        restore_board(snapshot_board(board))


def test_optimistic_lock_prevents_concurrent_capacity_overfill():
    repository = InMemoryKanbanRepository()
    events = EventBus()
    unit = SynchronousKanbanUnitOfWork(repository, events)
    facade = KanbanFacade(repository, unit)
    board = facade.create_board("owner", "Board")
    column = board.columns[0].id
    facade.update_board("owner", board.id, wip_groups=[WipGroup("Group", (column,), 1)])
    stale = restore_board(repository.get(board.id))
    facade.add_card("owner", board.id, column, "Winner")
    stale.cards["loser"] = Card("loser", title="Loser")
    stale.columns[column].card_ids.append("loser")
    with pytest.raises(ConcurrencyError):
        unit.save(snapshot_board(stale), (), expected_version=stale.version)
    assert len(facade.get_board("owner", board.id).cards) == 1


def test_automated_move_obeys_group_and_rolls_back_trigger():
    from kanban.spi import MoveCardAction

    class Runner:
        def evaluate(self, event, facts):
            if event.type == "card.updated":
                return (MoveCardAction(event.entity_id, facts.columns[1].id),)
            return ()

    repository = InMemoryKanbanRepository()
    events = EventBus()
    facade = KanbanFacade(
        repository,
        SynchronousKanbanUnitOfWork(repository, events),
        automation_runner=Runner(),
    )
    board = facade.create_board("owner", "Board")
    todo, doing = [col.id for col in board.columns[:2]]
    facade.update_board("owner", board.id, wip_groups=[WipGroup("Active", (doing,), 1)])
    facade.add_card("owner", board.id, doing, "Occupant")
    pending = facade.add_card("owner", board.id, todo, "Pending")
    before = facade.get_board("owner", board.id)
    event_count = len(events.get_events())
    with pytest.raises(ValidationError, match="Active"):
        facade.update_card("owner", board.id, pending.id, title="Changed")
    assert facade.get_board("owner", board.id) == before
    assert len(events.get_events()) == event_count
