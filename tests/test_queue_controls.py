from datetime import datetime, timedelta, timezone

import pytest

from kanban import KanbanFacade, ValidationError, WipGroup
from kanban.policies import AllowAllWorkflowPolicy
from kanban.spi import BlockCardAction
from kanban_adapters import (
    EventBus,
    InMemoryKanbanRepository,
    SynchronousKanbanUnitOfWork,
)


def test_queue_policies_age_and_batched_blocking_share_the_same_state():
    current_time = datetime(2026, 10, 11, tzinfo=timezone.utc)

    class ReviewPolicy(AllowAllWorkflowPolicy):
        def validate_move(self, context):
            if context.card.is_blocked:
                raise ValidationError("Resolve blockers first")
            if not context.card.attributes.get("handoff_verified"):
                raise ValidationError("Verified handoff required")

    class BlockAged:
        def evaluate(self, event, facts):
            if event.type != "board.tick":
                return ()
            limits = {column.id: column.max_age for column in facts.columns}
            return tuple(
                BlockCardAction(card.id, "Review overdue")
                for card in facts.cards
                if not card.archived
                and card.blocked_reason is None
                and card.entered_column_at is not None
                and limits[card.column_id] is not None
                and facts.now - card.entered_column_at > limits[card.column_id]
            )

    repo = InMemoryKanbanRepository()
    events = EventBus()
    facade = KanbanFacade(
        repo,
        SynchronousKanbanUnitOfWork(repo, events),
        workflow_policy=ReviewPolicy(),
        automation_runner=BlockAged(),
        clock=lambda: current_time,
    )
    board = facade.create_board(
        "alice", "Queue", ["Backlog", "Working", "Review", "Accepted"]
    )
    backlog, working, review, accepted = board.columns
    facade.update_board(
        "alice",
        board.id,
        wip_groups=[WipGroup("Unfinished", (working.id, review.id), 2)],
    )
    facade.update_column(
        "alice", board.id, review.id, policy={"max_age": timedelta(hours=1)}
    )
    first = facade.add_card("alice", board.id, backlog.id, "First")
    second = facade.add_card("alice", board.id, backlog.id, "Second")
    with pytest.raises(ValidationError, match="Verified handoff"):
        facade.move_card("alice", board.id, first.id, working.id)
    for card in (first, second):
        facade.update_card(
            "alice", board.id, card.id, attributes={"handoff_verified": True}
        )
        facade.move_card("alice", board.id, card.id, working.id)
        facade.move_card("alice", board.id, card.id, review.id)
    with pytest.raises(ValidationError, match="WIP group"):
        facade.add_card("alice", board.id, working.id, "Third")
    facade.block_card("alice", board.id, second.id, first.id)
    current_time += timedelta(hours=2)
    assert len(facade.aging_cards("alice", board.id).cards) == 2
    batch = facade.tick("alice", board.id, max_actions=1)
    assert len(batch.processed_card_ids) == len(batch.deferred_card_ids) == 1
    assert len(facade.tick("alice", board.id, max_actions=1).processed_card_ids) == 1
    assert facade.tick("alice", board.id).processed_card_ids == ()
    with pytest.raises(ValidationError, match="Resolve blockers"):
        facade.move_card("alice", board.id, first.id, accepted.id)
    facade.unblock_card_external("alice", board.id, second.id)
    restored = facade.get_board("alice", board.id).card(second.id)
    assert restored.blocked_by == frozenset({first.id})
    assert restored.blocked_reason is None and restored.is_blocked
    facade.unblock_card_external("alice", board.id, first.id)
    facade.move_card("alice", board.id, first.id, accepted.id)
    facade.unblock_card("alice", board.id, second.id, first.id)
    facade.move_card("alice", board.id, second.id, accepted.id)
    assert facade.aging_cards("alice", board.id).cards == ()
    assert all(
        card.attributes["handoff_verified"]
        for card in facade.get_board("alice", board.id).cards
    )
