# kanban-core

[![Tests](https://github.com/adieyal/kanban-core/actions/workflows/test.yml/badge.svg)](https://github.com/adieyal/kanban-core/actions/workflows/test.yml)

A framework-independent kanban business module for Python 3.10 and later.

The supported application API is deliberately narrow: callers invoke
`KanbanFacade` and receive immutable views. Domain objects, use cases and business
state remain behind that boundary. Persistence and event delivery are injected at
the application composition root.

## Installation

```bash
pip install kanban-core
```

## Usage

```python
from kanban import KanbanFacade
from kanban_adapters import (
    EventBus,
    InMemoryKanbanRepository,
    SynchronousKanbanUnitOfWork,
)

# Composition belongs in an entry point such as a web view, worker or command.
repository = InMemoryKanbanRepository()
events = EventBus()
unit_of_work = SynchronousKanbanUnitOfWork(repository, events)
kanban = KanbanFacade(repository, unit_of_work)

board = kanban.create_board("user-123", "Launch")
todo = board.column_named("To Do")
assert todo is not None

card = kanban.add_card(
    "user-123",
    board.id,
    todo.id,
    "Publish release notes",
)

in_progress = board.column_named("In Progress")
assert in_progress is not None
kanban.move_card("user-123", board.id, card.id, in_progress.id)
```

`kanban_adapters` contains reference infrastructure, not business logic. Replace
those adapters at the composition root when integrating a database or message
broker.

## Public contract

Only names in `kanban.__all__` are supported public API. In particular:

- `KanbanFacade` is the only business-operation entry point.
- `BoardView`, `ColumnView` and `CardView` are immutable return values.
- infrastructure and extension contracts live under `kanban.spi`; they are not
  part of the application API.
- modules containing models, services, automation and permissions are internal and
  may change without compatibility guarantees.

Version 2.0 removes the old command dispatch API, `SimpleKanban`, mutable domain
returns and top-level exports of internal services and models.

Version 2.1 adds a required atomic unit-of-work boundary, stable event-envelope
metadata and read-only workflow-policy contexts. See
[Extending the module](docs/extensibility.md).

## Development

```bash
python -m pip install -e ".[dev]"
make check
make test
```

The CI contract is pytest, Ruff formatting and linting, and strict mypy checking.

## License

MIT
