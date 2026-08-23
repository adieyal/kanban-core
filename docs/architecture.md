# Architecture

Kanban Core should own Kanban business truth without owning your framework or
infrastructure choices.

```text
                    application
                        |
                        v
                 +--------------+
                 | KanbanFacade |
                 +------+-------+
                        |
              application/domain
                        |
               depends on contracts
                        |
        +---------------+---------------+
        |               |               |
   repository       policies        automation/search
        ^               ^               ^
        |               |               |
        +------ infrastructure ----------+
```

## Why one facade?

A narrow facade gives callers one supported way to ask the business module to do
something. Controllers, jobs and adapters should not grow their own workflow rules.

## Why immutable views?

Returning mutable domain entities would let application code change business state
without authorization, validation, concurrency checks or events.

## Why snapshots at persistence?

`BoardSnapshot` lets infrastructure store state without gaining authority to mutate
the aggregate.

## Why detached extension contexts?

Extensions generally need facts, not authority over the aggregate:

- permissions receive `PermissionContext`;
- workflow rules receive policy contexts;
- search receives detached search cards;
- automation receives facts and proposes actions.

## Transaction and event boundary

`KanbanUnitOfWork` receives both state and resulting events so production adapters
can persist state and an outbox atomically.

## Where new behavior belongs

- new user-visible Kanban capability -> facade + internal business logic;
- deployment-specific validation -> `WorkflowPolicy`;
- authorization -> `PermissionPolicy`;
- persistence/search/event delivery -> SPI adapter;
- automatic reaction to events -> automation returning supported actions.
