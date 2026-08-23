# Clock and ID generation

`KanbanFacade` accepts a `Clock` and `IDFactory` to make tests and simulations
deterministic.

```python
from datetime import datetime, timezone

fixed_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
ids = iter(["board-1", "column-1", "column-2", "column-3", "card-1"])

kanban = KanbanFacade(
    repository,
    uow,
    clock=lambda: fixed_time,
    id_factory=lambda: next(ids),
)
```

Use these for repeatable tests, fixtures, simulations and controlled migration
tooling. Production applications can normally use the defaults.
