# Core concepts

Kanban Core is a business module, not a collection of models and utility classes.

## One application boundary

```text
HTTP view ----+
worker -------+--> KanbanFacade --> internal application/domain code
CLI command --+
```

Application code calls `KanbanFacade`. Internal services and domain objects are
implementation details.

## Views are observations

Facade methods return immutable `BoardView`, `ColumnView` and `CardView` values.

```python
board = kanban.get_board(user_id, board_id)
```

Treat `board` as a snapshot of what was true when the operation completed.

```python
# Wrong
board.name = "New name"
repository.save(board)

# Correct
board = kanban.update_board(user_id, board.id, name="New name")
```

## The module owns business truth

Structural invariants such as column existence, WIP limits, card ordering and
dependency cycles are enforced inside the module.

## Ports point outward

Kanban Core defines the contracts it needs; infrastructure implements them.

```text
business module ----depends on----> KanbanRepository
                                      ^
                                      |
                                Postgres adapter
```

## Composition happens at the edge

```python
repository = MyPostgresKanbanRepository(...)
uow = MyPostgresKanbanUnitOfWork(...)
permissions = MyPermissionPolicy(...)

kanban = KanbanFacade(
    repository,
    uow,
    permission_checker=permissions,
)
```

Create this object graph in an application entry point or composition root.

## Mutable domain objects do not cross the boundary

Persistence receives `BoardSnapshot`. Permission, workflow, search and automation
extensions receive detached contexts or facts. This keeps one owner for business
state and decisions.
