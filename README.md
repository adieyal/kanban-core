# Kanban Core Library

A comprehensive, extensible kanban board implementation designed with dependency injection in mind, allowing you to easily plug in external libraries for persistence, search, automation, or other advanced features.

## Features

- **Standard Library Only**: No external dependencies for core functionality
- **Extensible Architecture**: Plugin system for persistence, search, and automation
- **Thread-Safe**: Built-in concurrency support with optimistic locking
- **Event-Driven**: Comprehensive event system for audit trails and integrations
- **Permissions System**: Granular permission control with customizable checkers
- **Metrics & Analytics**: Built-in calculation of kanban metrics (cycle time, throughput, etc.)
- **Type Safe**: Full type hints for better IDE support and code quality

## Installation

```bash
pip install kanban-core
```

## Quick Start

```python
from kanban import SimpleKanban

# Create a kanban instance
kanban = SimpleKanban()

# Create a board
board = kanban.create_board("user_id", "My Project")

# Add some cards
card1 = kanban.add_card("user_id", board.id, "To Do", "Design the API")
card2 = kanban.add_card("user_id", board.id, "To Do", "Write tests")

# Move a card
kanban.move_card("user_id", board.id, card1.id, "In Progress")

# Search for cards
cards = kanban.search_cards("user_id", board.id, text="API")
```

## Advanced Usage

### Custom Repository

```python
from kanban import KanbanFacade, EventBus
from your_db import CustomRepository

repository = CustomRepository()
event_bus = EventBus()

kanban = KanbanFacade(repository, event_bus)
```

### Automation Rules

```python
from kanban import create_auto_move_rule

# Auto-move cards with "ready" label to "In Progress" column
rule = create_auto_move_rule("ready", "In Progress")
board.automation_rules.append(rule)
```

## Architecture

The library is organized into several key modules:

- **models**: Core domain objects (Board, Card, Column, etc.)
- **events**: Event system for audit trails and automation
- **repositories**: Data persistence layer with pluggable backends
- **services**: Business logic and workflow management
- **permissions**: Authorization and access control
- **metrics**: Kanban analytics and reporting
- **facade**: High-level API interfaces

## Development

### Setup

```bash
git clone https://github.com/redbaron/kanban-core
cd kanban-core
pip install -e ".[dev]"
pre-commit install
```

### Running Tests

```bash
pytest
```

### Code Quality

This project uses:
- **ruff** for linting and formatting
- **mypy** for type checking
- **pre-commit** for automated quality checks

```bash
ruff check .
ruff format .
mypy src/
```

## License

MIT License - see LICENSE file for details.