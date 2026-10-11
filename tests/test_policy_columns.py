from dataclasses import FrozenInstanceError
from datetime import timedelta

import pytest

from kanban import BoardImport, CardImport, ColumnImport, KanbanFacade, ValidationError
from kanban.policies import AllowAllWorkflowPolicy
from kanban.spi import ColumnPolicyContext, MoveCardAction
from kanban_adapters import (
    EventBus,
    InMemoryKanbanRepository,
    SynchronousKanbanUnitOfWork,
)


class PullGate(AllowAllWorkflowPolicy):
    observations = None

    def validate_move(self, context):
        self.observations = context
        assert context.from_column.id == context.from_column_id
        assert context.to_column.id == context.to_column_id
        if context.to_column.name != "Doing" or context.card.attributes.get("expedite"):
            return
        if any(
            column.name == "Review" and column.card_count >= 2
            for column in context.columns
        ):
            raise ValidationError("Finish reviews first")


def setup(runner=None):
    policy = PullGate()
    repo = InMemoryKanbanRepository()
    events = EventBus()
    facade = KanbanFacade(
        repo,
        SynchronousKanbanUnitOfWork(repo, events),
        workflow_policy=policy,
        automation_runner=runner,
    )
    board = facade.import_board(
        "owner",
        BoardImport(
            "queue",
            "Queue",
            "owner",
            (
                ColumnImport("ready", "Ready"),
                ColumnImport("doing", "Doing", wip_limit=1),
                ColumnImport("review", "Review", max_age=timedelta(hours=1)),
            ),
            (
                CardImport("new", "ready", "New"),
                CardImport("review1", "review", "First review"),
                CardImport("review2", "review", "Second review", archived=True),
            ),
        ),
    )
    return facade, board, policy, events


def test_policy_can_gate_moves_from_current_occupancy_and_names():
    facade, board, policy, events = setup()
    before = facade.get_board("owner", board.id)
    before_events = events.get_events()
    with pytest.raises(ValidationError, match="Finish reviews"):
        facade.move_card("owner", board.id, "new", "doing")
    assert facade.get_board("owner", board.id) == before
    assert events.get_events() == before_events
    context = policy.observations
    review = next(column for column in context.columns if column.name == "Review")
    assert isinstance(review, ColumnPolicyContext)
    assert review.card_count == 2 and review.max_age == timedelta(hours=1)
    assert context.from_column.name == "Ready" and context.to_column.wip_limit == 1
    with pytest.raises(FrozenInstanceError):
        review.card_count = 0
    facade.delete_card("owner", board.id, "review2")
    assert facade.move_card("owner", board.id, "new", "doing").column_id == "doing"
    assert review.card_count == 2  # Previously observed facts remain detached.


def test_host_expedite_rule_cannot_bypass_core_wip():
    facade, board, _, _ = setup()
    facade.update_card("owner", board.id, "new", attributes={"expedite": True})
    facade.move_card("owner", board.id, "new", "doing")
    card = facade.add_card(
        "owner", board.id, "ready", "Another", attributes={"expedite": True}
    )
    with pytest.raises(ValidationError, match="WIP"):
        facade.move_card("owner", board.id, card.id, "doing")


def test_automation_gate_uses_occupancy_after_earlier_action_in_same_transaction():
    class MoveBoth:
        def evaluate(self, event, facts):
            if event.type == "card.updated":
                return (
                    MoveCardAction("review1", "ready"),
                    MoveCardAction("new", "doing"),
                )
            return ()

    facade, board, policy, _ = setup(MoveBoth())
    facade.update_card("owner", board.id, "new", title="Trigger")
    assert facade.get_board("owner", board.id).card("new").column_id == "doing"
    assert (
        next(
            column.card_count
            for column in policy.observations.columns
            if column.id == "review"
        )
        == 1
    )


def test_create_update_delete_contexts_also_expose_detached_columns():
    class Observe(AllowAllWorkflowPolicy):
        seen = []

        def validate_create(self, context):
            self.seen.append(context)

        validate_update = validate_create
        validate_delete = validate_create

    policy = Observe()
    repo = InMemoryKanbanRepository()
    facade = KanbanFacade(
        repo, SynchronousKanbanUnitOfWork(repo, EventBus()), workflow_policy=policy
    )
    board = facade.create_board("owner", "Queue")
    card = facade.add_card("owner", board.id, board.columns[0].id, "Task")
    facade.update_card("owner", board.id, card.id, title="Updated")
    facade.delete_card("owner", board.id, card.id)
    assert len(policy.seen) == 3
    assert all(
        context.column(board.columns[0].id).card_count == 1 for context in policy.seen
    )
