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
