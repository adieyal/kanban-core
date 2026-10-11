import pytest

from kanban import ConcurrencyError, KanbanFacade, PermissionError, ValidationError
from kanban.policies import AllowAllWorkflowPolicy
from kanban.repositories import restore_board, snapshot_board
from kanban.spi import MoveCardAction
from kanban_adapters import (
    EventBus,
    InMemoryKanbanRepository,
    SynchronousKanbanUnitOfWork,
)


def environment(**kwargs):
    repository = InMemoryKanbanRepository()
    events = EventBus()
    facade = KanbanFacade(
        repository, SynchronousKanbanUnitOfWork(repository, events), **kwargs
    )
    board = facade.create_board("owner", "Queue")
    card = facade.add_card(
        "owner",
        board.id,
        board.columns[0].id,
        "Task",
        attributes={"keep": {"original": True}, "delete": 1, "replace": {"old": 1}},
    )
    return facade, board, card, repository, events


def test_patch_preserves_other_keys_sets_null_and_removes_explicitly():
    facade, board, card, _, events = environment()
    values = {"replace": {"new": [1]}, "nullable": None}
    patched = facade.patch_attributes(
        "owner", board.id, card.id, set=values, remove=["delete", "missing"]
    )
    assert dict(patched.attributes) == {
        "keep": {"original": True},
        "replace": {"new": (1,)},
        "nullable": None,
    }
    values["replace"]["new"].append(2)
    assert patched.attributes["replace"]["new"] == (1,)
    event = events.get_events()[-1]
    assert event.type == "card.updated"
    assert event.data["before"]["attributes"]["delete"] == 1
    assert event.data["after"]["attributes"]["nullable"] is None
    facade.update_card("owner", board.id, card.id, attributes={"replacement": True})
    assert dict(facade.get_board("owner", board.id).card(card.id).attributes) == {
        "replacement": True
    }


def test_repeated_or_empty_patch_is_a_noop():
    facade, board, card, repository, events = environment()
    facade.patch_attributes(
        "owner", board.id, card.id, set={"nullable": None}, remove=["delete"]
    )
    before = repository.get(board.id)
    before_events = events.get_events()
    facade.patch_attributes(
        "owner", board.id, card.id, set={"nullable": None}, remove=["delete"]
    )
    facade.patch_attributes("owner", board.id, card.id)
    assert repository.get(board.id) == before
    assert events.get_events() == before_events


@pytest.mark.parametrize(
    "kwargs",
    [
        {"set": {"key": 1}, "remove": ["key"]},
        {"remove": "delete"},
        {"remove": [1]},
        {"remove": [[]]},
        {"set": {"bad": float("nan")}},
    ],
)
def test_invalid_patch_is_atomic(kwargs):
    facade, board, card, repository, events = environment()
    before = repository.get(board.id)
    before_events = events.get_events()
    with pytest.raises(ValidationError):
        facade.patch_attributes("owner", board.id, card.id, **kwargs)
    assert repository.get(board.id) == before and events.get_events() == before_events


def test_patch_checks_permissions_and_policy_against_merged_attributes():
    class Reject(AllowAllWorkflowPolicy):
        def validate_update(self, context):
            assert context.attributes["keep"]["original"]
            if context.attributes.get("reject"):
                raise ValidationError("Rejected")

    facade, board, card, repository, events = environment(workflow_policy=Reject())
    before = repository.get(board.id)
    before_events = events.get_events()
    with pytest.raises(PermissionError):
        facade.patch_attributes("stranger", board.id, card.id, set={"a": 1})
    with pytest.raises(ValidationError, match="Rejected"):
        facade.patch_attributes("owner", board.id, card.id, set={"reject": True})
    assert repository.get(board.id) == before and events.get_events() == before_events


def test_invalid_automation_rolls_back_patch():
    class Runner:
        def evaluate(self, event, facts):
            return (
                (MoveCardAction(event.entity_id, "missing"),)
                if event.type == "card.updated"
                else ()
            )

    facade, board, card, repository, events = environment(automation_runner=Runner())
    before = repository.get(board.id)
    before_events = events.get_events()
    from kanban import NotFoundError

    with pytest.raises(NotFoundError):
        facade.patch_attributes("owner", board.id, card.id, set={"a": 1})
    assert repository.get(board.id) == before and events.get_events() == before_events


def test_patch_conflicting_write_preserves_competing_update():
    facade, board, card, repository, events = environment()
    unit_of_work = facade._core.unit_of_work

    class CompetingWrite:
        def save(self, snapshot, generated, expected_version=None):
            current = restore_board(repository.get(board.id))
            current.cards[card.id].attributes["concurrent"] = True
            repository.save(snapshot_board(current), expected_version=expected_version)
            return unit_of_work.save(
                snapshot, generated, expected_version=expected_version
            )

    facade._core.unit_of_work = CompetingWrite()
    before_events = events.get_events()
    with pytest.raises(ConcurrencyError):
        facade.patch_attributes("owner", board.id, card.id, set={"ours": True})
    stored = facade.get_board("owner", board.id).card(card.id)
    assert stored.attributes["concurrent"] and "ours" not in stored.attributes
    assert events.get_events() == before_events


@pytest.mark.parametrize(
    "before,after",
    [
        (1, True),
        (True, 1),
        (0, False),
        (False, 0),
        (1, 1.0),
        ({"nested": [1]}, {"nested": [True]}),
    ],
)
@pytest.mark.parametrize("operation", ["patch", "replace"])
def test_json_type_changes_are_validated_emitted_and_persisted(
    before, after, operation
):
    class Observe(AllowAllWorkflowPolicy):
        observations = []

        def validate_update(self, context):
            self.observations.append(context)

    policy = Observe()
    facade, board, card, repository, events = environment(workflow_policy=policy)
    facade.update_card("owner", board.id, card.id, attributes={"value": before})
    version = repository.get(board.id).version
    before_events = len(events.get_events())
    policy.observations.clear()
    if operation == "patch":
        result = facade.patch_attributes(
            "owner", board.id, card.id, set={"value": after}
        )
    else:
        result = facade.update_card(
            "owner", board.id, card.id, attributes={"value": after}
        )
    stored = facade.get_board("owner", board.id).card(card.id)
    assert repository.get(board.id).version == version + 1
    assert len(policy.observations) == 1
    assert len(events.get_events()) == before_events + 1
    assert type(stored.attributes["value"]) is type(result.attributes["value"])
    assert stored.attributes == result.attributes
    if isinstance(after, dict):
        assert type(stored.attributes["value"]["nested"][0]) is bool
    else:
        assert type(stored.attributes["value"]) is type(after)
