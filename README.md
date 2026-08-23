# kanban-core

[![Tests](https://github.com/adieyal/kanban-core/actions/workflows/test.yml/badge.svg)](https://github.com/adieyal/kanban-core/actions/workflows/test.yml)

A framework-independent Kanban business module for Python 3.10+.

Your application talks to one public business API, `KanbanFacade`. The module owns
its business state and invariants; persistence, authorization, search, automation
and event delivery are supplied from outside at composition time.

```text
your application
      |
      v
+----------------+
| KanbanFacade   |  public business API
+--------+-------+
         |
  kanban business module
         |
   outbound contracts
         |
   infrastructure
```

## Quick example

```python
from kanban import KanbanFacade
from kanban_adapters import (
    EventBus,
    InMemoryKanbanRepository,
    SynchronousKanbanUnitOfWork,
)

repository = InMemoryKanbanRepository()
events = EventBus()
uow = SynchronousKanbanUnitOfWork(repository, events)
kanban = KanbanFacade(repository, uow)

board = kanban.create_board("alice", "Launch")
todo = board.column_named("To Do")
in_progress = board.column_named("In Progress")
assert todo is not None and in_progress is not None

card = kanban.add_card("alice", board.id, todo.id, "Publish release notes")
kanban.move_card("alice", board.id, card.id, in_progress.id)
```

`BoardView`, `ColumnView` and `CardView` are immutable observations. Change
business state only through `KanbanFacade`.

## Documentation

- **[Quickstart](docs/quickstart.md)** — build and use a board in a few minutes.
- **[Core concepts](docs/concepts.md)** — the facade boundary, immutable views,
  ports and composition.
- **[Extending Kanban Core](docs/extensibility.md)** — persistence, permissions,
  workflow rules, search, automation and events.
- **[Integration patterns](docs/integration-patterns.md)** — compose the module in
  web requests, workers and commands.
- **[API reference](docs/api-reference.md)** — supported facade, views, exceptions
  and SPI contracts.
- **[Architecture](docs/architecture.md)** — why the module is designed this way.

## Public contract

Only names in `kanban.__all__` are supported application API:

- `KanbanFacade` is the only business-operation entry point.
- `BoardView`, `ColumnView` and `CardView` are immutable return values.
- public exceptions are exported from `kanban`.
- infrastructure and extension contracts live under `kanban.spi`.

Internal models and application services are implementation details.

## Development

```bash
python -m pip install -e ".[dev]"
make check
make test
```

## License

MIT
