"""Tests for the reduced v2 aggregate model."""

from datetime import datetime, timezone

import pytest

from kanban import ValidationError
from kanban.models import Board, Card, Column, ColumnPolicy


def test_card_is_blocked_by_dependencies() -> None:
    card = Card(id="card-1", blocked_by={"card-0"})

    assert card.is_blocked()


def test_column_wip_policy_rejects_new_entry_at_limit() -> None:
    column = Column(
        id="todo",
        board_id="board-1",
        policy=ColumnPolicy(wip_limit=1),
        card_ids=["card-1"],
    )

    accepted, reason = column.can_accept_card(is_new_entry=True)

    assert not accepted
    assert reason == "WIP limit of 1 would be exceeded."


def test_board_orders_columns_and_finds_card_column() -> None:
    board = Board(
        id="board-1",
        created_at=datetime.now(timezone.utc),
        columns={
            "done": Column(id="done", board_id="board-1", position=1),
            "todo": Column(
                id="todo", board_id="board-1", position=0, card_ids=["card-1"]
            ),
        },
        cards={"card-1": Card(id="card-1")},
    )

    assert [column.id for column in board.get_columns_ordered()] == ["todo", "done"]
    assert board.column_for_card("card-1").id == "todo"


def test_board_rejects_unknown_card_column_lookup() -> None:
    with pytest.raises(ValidationError, match="card-1"):
        Board(id="board-1").column_for_card("card-1")
