"""Attributes stay opaque while policies and automation can inspect them safely."""

import json
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from kanban import KanbanFacade, ValidationError
from kanban.models import Board, Card, Column
from kanban.policies import AllowAllWorkflowPolicy
from kanban.repositories import FrozenMap, restore_board, snapshot_board
from kanban.spi import AutomationCardFacts
from kanban_adapters import (
    EventBus,
    InMemoryKanbanRepository,
    SynchronousKanbanUnitOfWork,
)


def make_facade(**options):
    repository = InMemoryKanbanRepository()
    events = EventBus()
    facade = KanbanFacade(
        repository, SynchronousKanbanUnitOfWork(repository, events), **options
    )
    board = facade.create_board("alice", "Queue")
    return facade, board, events


def test_attributes_replace_and_detach_nested_caller_data() -> None:
    facade, board, events = make_facade()
    attributes = {"handoffs": [{"review": "accepted"}], "obsolete": True}
    card = facade.add_card(
        "alice", board.id, board.columns[0].id, "Task", attributes=attributes
    )
    attributes["handoffs"][0]["review"] = "changed"
    assert card.attributes["handoffs"][0]["review"] == "accepted"
    with pytest.raises(TypeError):
        card.attributes["obsolete"] = False
    with pytest.raises(TypeError):
        card.attributes["handoffs"][0]["review"] = "changed"
    assert isinstance(card.attributes["handoffs"], tuple)

    replacement = {"verdict": {"approved": True, "scores": [1, 2.5, None]}}
    updated = facade.update_card("alice", board.id, card.id, attributes=replacement)
    replacement["verdict"]["approved"] = False
    assert set(updated.attributes) == {"verdict"}
    assert updated.attributes["verdict"]["approved"] is True
    assert card.attributes["obsolete"] is True
    assert (
        facade.get_board("alice", board.id).card(card.id).attributes
        == updated.attributes
    )
    event = events.get_events()[-1]
    assert event.type == "card.updated"
    assert event.data["before"]["attributes"]["obsolete"] is True
    assert event.data["after"]["attributes"]["verdict"]["approved"] is True
    json.dumps(event.to_dict())

    # Public immutable read representations can be submitted without a custom thaw.
    version = facade.get_board("alice", board.id).version
    event_count = len(events.get_events())
    facade.update_card("alice", board.id, card.id, attributes=updated.attributes)
    assert facade.get_board("alice", board.id).version == version
    assert len(events.get_events()) == event_count
    cleared = facade.update_card("alice", board.id, card.id, attributes={})
    assert cleared.attributes == {}


@pytest.mark.parametrize(
    "attributes",
    [
        None,
        [],
        {1: "bad key"},
        {"nested": {1: "bad key"}},
        {"bad": {1, 2}},
        {"bad": datetime.now(timezone.utc)},
        {"bad": object()},
        {"bad": float("nan")},
        {"bad": float("inf")},
        {"bad": float("-inf")},
    ],
)
def test_invalid_attributes_reject_create_and_update_atomically(attributes) -> None:
    facade, board, events = make_facade()
    card = facade.add_card(
        "alice", board.id, board.columns[0].id, "Task", attributes={"safe": True}
    )
    before = facade.get_board("alice", board.id)
    event_count = len(events.get_events())
    with pytest.raises(ValidationError):
        facade.add_card(
            "alice", board.id, board.columns[0].id, "Invalid", attributes=attributes
        )
    with pytest.raises(ValidationError):
        facade.update_card(
            "alice", board.id, card.id, title="Changed", attributes=attributes
        )
    assert facade.get_board("alice", board.id) == before
    assert len(events.get_events()) == event_count


def test_cycles_reject_cleanly_and_repeated_shared_values_are_valid() -> None:
    facade, board, _ = make_facade()
    cycle = []
    cycle.append(cycle)
    with pytest.raises(ValidationError, match="cycles"):
        facade.add_card(
            "alice", board.id, board.columns[0].id, "Task", attributes={"cycle": cycle}
        )
    cycle_dict = {}
    cycle_dict["self"] = cycle_dict
    with pytest.raises(ValidationError, match="cycles"):
        facade.add_card(
            "alice", board.id, board.columns[0].id, "Task", attributes=cycle_dict
        )
    shared = {"value": 1}
    card = facade.add_card(
        "alice",
        board.id,
        board.columns[0].id,
        "Task",
        attributes={"a": shared, "b": shared},
    )
    assert card.attributes["a"] == card.attributes["b"] == {"value": 1}


def test_policy_and_automation_receive_candidate_attributes_without_lookup() -> None:
    contexts = []
    facts_seen = []

    class Policy(AllowAllWorkflowPolicy):
        def validate_create(self, context):
            contexts.append(context)

        def validate_update(self, context):
            contexts.append(context)
            if context.attributes["verdict"] != "accepted":
                raise ValidationError("Review required")

        def validate_move(self, context):
            contexts.append(context.card)

        def validate_delete(self, context):
            contexts.append(context)

    class Runner:
        def evaluate(self, event, facts):
            facts_seen.extend(facts.cards)
            return ()

    facade, board, _ = make_facade(workflow_policy=Policy(), automation_runner=Runner())
    card = facade.add_card(
        "alice",
        board.id,
        board.columns[0].id,
        "Task",
        attributes={"verdict": "pending", "handoffs": [{"id": "worker"}]},
    )
    with pytest.raises(ValidationError, match="Review required"):
        facade.update_card(
            "alice", board.id, card.id, attributes={"verdict": "rejected"}
        )
    assert (
        facade.get_board("alice", board.id).card(card.id).attributes["verdict"]
        == "pending"
    )
    facade.update_card(
        "alice",
        board.id,
        card.id,
        attributes={"verdict": "accepted", "handoffs": [{"id": "reviewer"}]},
    )
    facade.move_card("alice", board.id, card.id, board.columns[1].id)
    facade.delete_card("alice", board.id, card.id)
    assert [context.attributes["verdict"] for context in contexts] == [
        "pending",
        "rejected",
        "accepted",
        "accepted",
        "accepted",
    ]
    for context in [contexts[0], facts_seen[0]]:
        with pytest.raises(TypeError):
            context.attributes["handoffs"][0]["id"] = "changed"
    assert contexts[0].attributes["handoffs"][0]["id"] == "worker"
    assert facts_seen[-1].attributes["verdict"] == "accepted"


def test_snapshot_preserves_json_container_shapes_and_old_defaults() -> None:
    attributes = {
        "empty_object": {},
        "empty_array": [],
        "nested": [{"data": [True, None, 1, 2.5, "text"]}],
    }
    card = Card("card", attributes=attributes)
    board = Board(
        "board",
        owner_id="alice",
        cards={card.id: card},
        columns={"todo": Column("todo", "board", card_ids=[card.id])},
    )
    snapshot = snapshot_board(board)
    restored = restore_board(snapshot)
    assert restored.cards[card.id].attributes == attributes
    assert isinstance(restored.cards[card.id].attributes["nested"], list)
    assert isinstance(restored.cards[card.id].attributes["empty_object"], dict)
    restored.cards[card.id].attributes["nested"][0]["data"].append("changed")
    assert restore_board(snapshot).cards[card.id].attributes == attributes

    state = dict(snapshot.state)
    old_card = FrozenMap(
        tuple(
            (key, value)
            for key, value in dict(state["cards"])[card.id]
            if key != "attributes"
        )
    )
    state["cards"] = FrozenMap(((card.id, old_card),))
    old_snapshot = replace(snapshot, state=FrozenMap(tuple(state.items())))
    assert restore_board(old_snapshot).cards[card.id].attributes == {}


def test_direct_automation_facts_detach_nested_attributes() -> None:
    attributes = {"nested": [{"value": 1}]}
    facts = AutomationCardFacts("card", "todo", "Task", None, False, attributes)
    attributes["nested"][0]["value"] = 2
    assert facts.attributes["nested"][0]["value"] == 1
    with pytest.raises(TypeError):
        facts.attributes["nested"][0]["value"] = 3
