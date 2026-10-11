from datetime import datetime, timezone

import pytest

from kanban import KanbanFacade, ValidationError
from kanban.policies import AllowAllWorkflowPolicy
from kanban.spi import BlockCardAction, MoveCardAction
from kanban_adapters import (
    EventBus,
    InMemoryKanbanRepository,
    SynchronousKanbanUnitOfWork,
)


def setup(**kwargs):
    repository = InMemoryKanbanRepository()
    events = EventBus()
    facade = KanbanFacade(
        repository, SynchronousKanbanUnitOfWork(repository, events), **kwargs
    )
    board = facade.create_board("owner", "Board")
    card = facade.add_card("owner", board.id, board.columns[0].id, "Card")
    return facade, board, card, events


def test_external_block_is_independent_and_idempotent():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    facade, board, card, events = setup(clock=lambda: now)
    blocker = facade.add_card("owner", board.id, board.columns[0].id, "Dependency")
    facade.block_card("owner", board.id, card.id, blocker.id)
    facade.block_card_external("owner", board.id, card.id, "Awaiting vendor")
    blocked = facade.get_board("owner", board.id)
    assert blocked.card(card.id).blocked_at == now
    assert blocked.card(card.id).is_blocked
    facade.block_card_external("owner", board.id, card.id, "Awaiting vendor")
    assert facade.get_board("owner", board.id).version == blocked.version
    assert (
        len([e for e in events.get_events() if e.type == "card.externally_blocked"])
        == 1
    )
    facade.unblock_card_external("owner", board.id, card.id)
    unblocked = facade.get_board("owner", board.id).card(card.id)
    assert unblocked.blocked_by == frozenset({blocker.id})
    assert unblocked.is_blocked
    assert unblocked.blocked_at is None
    assert events.get_events()[-1].data["reason"] == "Awaiting vendor"


@pytest.mark.parametrize("reason", ["", "   ", 4, None])
def test_invalid_reason_rolls_back(reason):
    facade, board, card, events = setup()
    before = facade.get_board("owner", board.id)
    count = len(events.get_events())
    with pytest.raises(ValidationError):
        facade.block_card_external("owner", board.id, card.id, reason)
    assert facade.get_board("owner", board.id) == before
    assert len(events.get_events()) == count


def test_automation_uses_policy_and_rolls_back_all_actions():
    class Reject(AllowAllWorkflowPolicy):
        def validate_update(self, context):
            assert context.blocked_reason == "Stop"
            assert context.is_blocked
            raise ValidationError("rejected")

    class Runner:
        def evaluate(self, event, facts):
            if event.type == "card.updated":
                card = facts.cards[0]
                return (
                    MoveCardAction(card.id, facts.columns[1].id),
                    BlockCardAction(card.id, "Stop"),
                )
            return ()

    facade, board, card, events = setup(automation_runner=Runner())

    # Apply the rejecting policy only after the primary update has validated.
    class Policy(Reject):
        def validate_update(self, context):
            if context.blocked_reason is not None:
                super().validate_update(context)

    facade, board, card, events = setup(
        automation_runner=Runner(), workflow_policy=Policy()
    )
    before = facade.get_board("owner", board.id)
    count = len(events.get_events())
    with pytest.raises(ValidationError, match="rejected"):
        facade.update_card("owner", board.id, card.id, title="Changed")
    assert facade.get_board("owner", board.id) == before
    assert len(events.get_events()) == count


def test_automation_block_repeats_terminate_and_expose_facts():
    class Runner:
        def evaluate(self, event, facts):
            if event.type == "card.created":
                return (BlockCardAction(event.entity_id, "Stop"),)
            if event.type == "card.externally_blocked":
                card = facts.card(event.entity_id)
                assert card.is_blocked and card.blocked_reason == "Stop"
                assert card.blocked_at is not None
                return (BlockCardAction(card.id, "Stop"),)
            return ()

    facade, board, card, events = setup(automation_runner=Runner())
    assert facade.get_board("owner", board.id).card(card.id).blocked_reason == "Stop"
    assert (
        len([e for e in events.get_events() if e.type == "card.externally_blocked"])
        == 1
    )


def test_external_block_restore_validation_and_historic_defaults():
    from dataclasses import replace

    from kanban.models import Board, Card, Column
    from kanban.repositories import FrozenMap, restore_board, snapshot_board
    from kanban.spi import InvalidPersistenceStateError

    board = Board(
        "board",
        owner_id="owner",
        columns={"column": Column("column", "board", card_ids=["card"])},
        cards={"card": Card("card")},
    )
    snapshot = snapshot_board(board)
    old_cards = FrozenMap(
        tuple(
            (
                card_id,
                FrozenMap(
                    tuple(
                        (key, value)
                        for key, value in state
                        if key not in {"blocked_reason", "blocked_at"}
                    )
                ),
            )
            for card_id, state in dict(snapshot.state)["cards"]
        )
    )
    historic = replace(
        snapshot,
        state=FrozenMap(
            tuple(
                (key, old_cards if key == "cards" else value)
                for key, value in snapshot.state
            )
        ),
    )
    assert restore_board(historic).cards["card"].blocked_reason is None
    board.cards["card"].blocked_reason = "Stop"
    with pytest.raises(InvalidPersistenceStateError, match="external block"):
        restore_board(snapshot_board(board))
