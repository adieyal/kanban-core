# Workflow policies

`WorkflowPolicy` adds deployment-specific lifecycle rules.

```python
from kanban import ValidationError
from kanban.spi import CardMovePolicyContext, CardPolicyContext


class ReleaseWorkflow:
    def __init__(self, review_column_id: str):
        self.review_column_id = review_column_id

    def validate_create(self, context: CardPolicyContext) -> None:
        pass

    def validate_update(self, context: CardPolicyContext) -> None:
        pass

    def validate_move(self, context: CardMovePolicyContext) -> None:
        if (
            context.to_column_id == self.review_column_id
            and not context.card.assignee_ids
        ):
            raise ValidationError("Cards must be assigned before review")

    def validate_delete(self, context: CardPolicyContext) -> None:
        pass
```

Inject it with `workflow_policy=ReleaseWorkflow(...)`.

Permission asks **may this user do this?** Workflow asks **is this proposed state or
transition valid?**

Structural invariants remain owned by Kanban Core.

## Column observations and pull gates

`CardPolicyContext.columns` is a tuple of immutable `ColumnPolicyContext` values:
`id`, `name`, `card_count`, `wip_limit` and `max_age`. Use `context.column(id)` to
look up a column. `CardMovePolicyContext` exposes the same tuple through `columns`
and supplies `from_column` and `to_column` lookups alongside the existing IDs.
Core-produced move contexts always contain those columns. Manual contexts with
no matching observation return `None` from a lookup.

Occupancy comes from the board inside the current operation, including earlier
automation actions. It counts all cards occupying a column, including archived
cards, consistently with WIP limits. Move facts describe the state before the
proposed move. Creation facts include the proposed card; update facts include
proposed field changes; deletion facts precede removal. Previously observed
contexts remain unchanged after later operations.

For example, a host can forbid starting more work while reviews are backed up:

```python
def validate_move(self, context: CardMovePolicyContext) -> None:
    destination = context.to_column
    if destination is None or destination.name != "Doing":
        return
    if context.card.attributes.get("expedite"):
        return
    if any(column.name == "Review" and column.card_count >= 2
           for column in context.columns):
        raise ValidationError("Finish reviews before starting new work")
```

Thresholds and the meaning of `expedite` belong to this host policy. An exception
in a policy does not bypass core column or group WIP limits. IDs remain the stable
identity when a host renames columns; names are observations, not a second ID.
