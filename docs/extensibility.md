# Extending the business module

Extensions enter through constructor-injected ports. They do not receive mutable
domain aggregates and do not add alternate command paths around `KanbanFacade`.
Application callers import the facade, immutable views and exceptions from
`kanban`. Infrastructure and extension implementations import contracts only from
`kanban.spi`.

## Workflow rules

Implement `WorkflowPolicy` for deployment-specific validation. Each method gets a
detached, frozen context describing the proposed card state. Raise
`ValidationError` to reject an operation.

```python
from kanban import ValidationError
from kanban.spi import CardPolicyContext, WorkflowPolicy


class ReleasePolicy(WorkflowPolicy):
    def validate_create(self, context: CardPolicyContext) -> None:
        pass

    def validate_update(self, context: CardPolicyContext) -> None:
        if context.archived and not context.assignee_ids:
            raise ValidationError("Archived cards must retain an owner")

    def validate_move(self, context) -> None:
        pass

    def validate_delete(self, context: CardPolicyContext) -> None:
        pass
```

Structural invariants such as column existence, WIP limits, ordering and dependency
cycles remain owned by the module. A workflow policy adds rules; it cannot replace
those invariants or mutate state.

## Atomic state and events

`SynchronousKanbanUnitOfWork` provides save-then-publish behavior for tests and
single-process deployments. It cannot prevent event loss if the process fails after
saving and before publishing.

For durable integrations, implement `KanbanUnitOfWork` so `save` or `delete` and
outbox insertion occur in one database transaction. The outbox relay belongs to
infrastructure. Inject the implementation at composition:

```python
kanban = KanbanFacade(
    repository,
    PostgresKanbanUnitOfWork(...),
)
```

The port receives events before an aggregate version is assigned. A `save`
implementation must record each event with the version assigned to its returned
board. `emit` handles events produced without a state change.

## Event compatibility

Every event carries:

- `schema_version`, initially `1`;
- `correlation_id`, shared by one facade operation and its automation chain;
- `causation_id`, identifying the event that caused an automation event;
- `aggregate_version`, assigned at the commit boundary.

Consumers should route on event type and schema version, ignore unknown additive
fields, and treat an event ID as an idempotency key. Changing the meaning or shape of
an existing payload requires a new schema version.

## Boundary constraint

Application code must not import `kanban.models`, call services, or mutate repository
results. Infrastructure adapters depend only on `kanban.spi` and must not expose SPI
objects as an alternate application API. New business behavior should enter through
an SPI policy port or a new facade capability.
