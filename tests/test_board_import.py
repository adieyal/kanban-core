from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from kanban import (
    BoardImport,
    CardImport,
    ColumnImport,
    ConcurrencyError,
    KanbanFacade,
    PermissionError,
    ValidationError,
    WipGroup,
)
from kanban.policies import AllowAllWorkflowPolicy
from kanban_adapters import (
    EventBus,
    InMemoryKanbanRepository,
    SynchronousKanbanUnitOfWork,
)


def environment(**options):
    repository = InMemoryKanbanRepository()
    events = EventBus()
    facade = KanbanFacade(
        repository, SynchronousKanbanUnitOfWork(repository, events), **options
    )
    return facade, repository, events


def record():
    known = datetime(2020, 1, 1, tzinfo=timezone.utc)
    return BoardImport(
        "board",
        "History",
        "owner",
        (ColumnImport("review", "Review", max_age=timedelta(hours=1)),),
        (
            CardImport(
                "old",
                "review",
                "Old",
                attributes={"nested": [1, {"verified": True}]},
                created_at=known,
                entered_column_at=known,
                blocked_reason="Vendor",
                blocked_at=known,
            ),
            CardImport("unknown", "review", "Unknown", blocked_by=frozenset({"old"})),
        ),
        created_at=known,
        updated_at=known,
    )


def test_import_preserves_history_order_identity_and_unknown_times():
    facade, repository, events = environment()
    imported = facade.import_board("owner", record())
    assert imported.id == "board" and imported.version == 1
    assert imported.columns[0].card_ids == ("old", "unknown")
    old, unknown = imported.cards
    assert (
        old.created_at == old.entered_column_at == old.blocked_at == record().created_at
    )
    assert old.blocks == frozenset({"unknown"})
    assert unknown.blocked_by == frozenset({"old"}) and unknown.is_blocked
    assert unknown.created_at is None and unknown.entered_column_at is None
    assert imported == facade.get_board("owner", imported.id)
    assert repository.get(imported.id) is not None
    assert [event.type for event in events.get_events()] == ["board.imported"]
    assert events.get_events()[0].data == {"card_count": 2}
    assert events.get_events()[0].aggregate_version == 1
    result = facade.aging_cards("owner", imported.id)
    assert tuple(card.id for card in result.cards) == ("old",)
    assert tuple(card.id for card in result.unknown_age_cards) == ("unknown",)
    with pytest.raises(TypeError):
        old.attributes["nested"][1]["verified"] = False


def test_import_does_not_replay_workflow_or_automation_and_preserves_overfull_history():
    class Reject(AllowAllWorkflowPolicy):
        def validate_create(self, context):
            raise AssertionError("History is not new work")

    class Runner:
        def evaluate(self, event, facts):
            raise AssertionError("Import must not replay automation")

    facade, _, events = environment(
        workflow_policy=Reject(), automation_runner=Runner()
    )
    data = record()
    data = replace(
        data,
        columns=(replace(data.columns[0], wip_limit=1),),
        wip_groups=(WipGroup("reviewing", ("review",), 1),),
    )
    board = facade.import_board("owner", data)
    assert len(board.cards) == 2
    assert len(events.get_events()) == 1
    with pytest.raises(ValidationError, match="WIP"):
        facade.add_card("owner", board.id, "review", "New")


@pytest.mark.parametrize(
    "data",
    [
        replace(record(), id=""),
        replace(record(), columns=record().columns * 2),
        replace(record(), cards=record().cards * 2),
        replace(record(), cards=(replace(record().cards[0], column_id="missing"),)),
        replace(
            record(),
            cards=(replace(record().cards[0], blocked_by=frozenset({"missing"})),),
        ),
        replace(
            record(), cards=(replace(record().cards[0], blocked_by=frozenset({"old"})),)
        ),
        replace(
            record(),
            cards=(
                replace(record().cards[0], blocked_by=frozenset({"unknown"})),
                record().cards[1],
            ),
        ),
        replace(
            record(),
            cards=(replace(record().cards[0], entered_column_at=datetime(2020, 1, 1)),),
        ),
        replace(record(), cards=(replace(record().cards[0], blocked_at=None),)),
        replace(record(), columns=(ColumnImport("review", "Review", wip_limit=-1),)),
        replace(record(), wip_groups=(WipGroup("bad", ("missing",), 1),)),
    ],
)
def test_invalid_import_is_atomic(data):
    facade, repository, events = environment()
    with pytest.raises(ValidationError):
        facade.import_board("owner", data)
    assert repository.list_all() == []
    assert events.get_events() == []


def test_import_requires_permission_and_cannot_overwrite_existing_board():
    facade, repository, events = environment()
    with pytest.raises(PermissionError):
        facade.import_board("stranger", record())
    original = facade.import_board("owner", record())
    before_events = events.get_events()
    with pytest.raises(ConcurrencyError):
        facade.import_board("owner", replace(record(), name="Overwrite"))
    assert facade.get_board("owner", original.id) == original
    assert events.get_events() == before_events
    assert repository.get(original.id).version == 1


def test_permission_policy_can_deny_import_even_for_owner():
    class Deny:
        def has_permission(self, user_id, context, permission):
            return False

    facade, repository, events = environment(permission_checker=Deny())
    with pytest.raises(PermissionError):
        facade.import_board("owner", record())
    assert repository.list_all() == [] and events.get_events() == []


def test_import_inputs_detach_caller_containers():
    attributes = {"nested": [1]}
    blockers = {"old"}
    card = CardImport(
        "unknown", "review", "Unknown", attributes=attributes, blocked_by=blockers
    )
    cards = [record().cards[0], card]
    columns = list(record().columns)
    data = BoardImport("board", "History", "owner", columns, cards)
    attributes["nested"].append(2)
    blockers.clear()
    cards.clear()
    columns.clear()
    facade, _, _ = environment()
    imported = facade.import_board("owner", data)
    assert imported.card("unknown").attributes["nested"] == (1,)
    assert imported.card("unknown").blocked_by == frozenset({"old"})


@pytest.mark.parametrize(
    "field,value",
    [
        ("description", []),
        ("archived", []),
        ("size", []),
        ("size", float("inf")),
        ("column_id", []),
    ],
)
def test_card_import_rejects_mutable_or_invalid_scalar_fields(field, value):
    with pytest.raises(ValidationError):
        replace(record().cards[0], **{field: value})


def test_other_import_records_reject_mutable_scalar_fields():
    with pytest.raises(ValidationError):
        replace(record(), description=[])
    with pytest.raises(ValidationError):
        replace(record().columns[0], color=[])
