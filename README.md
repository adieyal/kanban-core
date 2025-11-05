# Kanban Core Library

[![Tests](https://github.com/redbaron/kanban-core/workflows/Tests/badge.svg)](https://github.com/redbaron/kanban-core/actions)
[![Coverage](https://codecov.io/gh/redbaron/kanban-core/branch/main/graph/badge.svg)](https://codecov.io/gh/redbaron/kanban-core)
[![PyPI version](https://badge.fury.io/py/kanban-core.svg)](https://badge.fury.io/py/kanban-core)
[![Python versions](https://img.shields.io/pypi/pyversions/kanban-core.svg)](https://pypi.org/project/kanban-core/)

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

## Important Limitations

### Serialization of Automation Rules and Column Policies

**Limitation**: `AutomationRule` and `ColumnPolicy` objects that contain Python callable functions (triggers, actions, entry/exit criteria) cannot be serialized to JSON or persisted to databases using standard serialization methods.

**Impact**:
- Boards with custom automation rules or column policies with callables cannot be directly serialized
- Custom repository implementations need special handling for these objects
- Boards cannot be easily transmitted over network or saved to disk with their automation logic

**Workarounds**:
1. **Separate Storage**: Store automation rules separately from board data, reconstructing them on application startup
2. **Rule Registry**: Maintain a registry of named rules that can be referenced by ID:
   ```python
   RULE_REGISTRY = {
       "auto-move-ready": create_auto_move_rule("ready", "In Progress"),
       "due-date-warning": create_due_date_warning_rule(3)
   }

   # Store only rule IDs with the board
   board_data = {
       "id": "board1",
       "rule_ids": ["auto-move-ready", "due-date-warning"]
   }
   ```
3. **Exclude from Serialization**: Remove automation rules and custom policies before serialization:
   ```python
   def serialize_board(board):
       board_copy = copy.copy(board)
       board_copy.automation_rules = []  # Exclude rules
       return json.dumps(board_copy.to_dict())
   ```

**Future Plans**: We plan to introduce a serializable rule definition language (DSL or expression-based) in a future version to enable full board serialization.

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
# Run tests
make test

# Run tests with coverage
make test-cov

# Generate HTML coverage report
make coverage-html
```

The project maintains high test coverage. View the latest coverage report in `htmlcov/index.html` after running `make coverage-html`.

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