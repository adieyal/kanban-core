# Persistence and atomic commits

Use this extension point when Kanban state should live in your application's
database.

## Repository boundary

`KanbanRepository` stores immutable `BoardSnapshot` records:

```python
from kanban.spi import BoardSnapshot


class PostgresKanbanRepository:
    def get(self, board_id: str) -> BoardSnapshot | None: ...

    def save(
        self,
        board: BoardSnapshot,
        expected_version: int | None = None,
    ) -> BoardSnapshot: ...

    def delete(self, board_id: str, expected_version: int) -> None: ...

    def list_all(self) -> list[BoardSnapshot]: ...

    def exists(self, board_id: str) -> bool: ...
```

Treat `BoardSnapshot` as an opaque persistence record. Infrastructure does not
receive mutable `Board` objects.

## Optimistic concurrency

`expected_version` protects against lost updates. Raise `ConcurrencyError` when the
stored version differs from the expected version.

## Repository vs unit of work

The repository stores snapshots. `KanbanUnitOfWork` defines the atomic commit of a
snapshot and the events caused by the same operation.

```python
class PostgresKanbanUnitOfWork:
    def save(self, board, events, expected_version=None):
        # one DB transaction:
        # 1. save snapshot
        # 2. append events to outbox
        # 3. commit
        ...
```

For production, an outbox is preferable to "save, then publish".

## Composition

```python
kanban = KanbanFacade(
    PostgresKanbanRepository(...),
    PostgresKanbanUnitOfWork(...),
)
```
