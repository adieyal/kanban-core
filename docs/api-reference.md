# API Reference

This document provides detailed API documentation for the main classes and methods in the Kanban Core Library.

## Table of Contents

- [SimpleKanban](#simplekanban)
- [KanbanFacade](#kanbanfacade)
- [Models](#models)
  - [Board](#board)
  - [Card](#card)
  - [Column](#column)
  - [Comment](#comment)
- [Repositories](#repositories)
  - [RepositoryInterface](#repositoryinterface)
- [Events](#events)
  - [EventBus](#eventbus)
  - [Event](#event)
- [Permissions](#permissions)
  - [PermissionChecker](#permissionchecker)
- [Exceptions](#exceptions)

## SimpleKanban

The simplest way to use the library. Uses in-memory storage.

```python
from kanban import SimpleKanban

kanban = SimpleKanban()
```

### Methods

#### create_board(user_id: str, name: str) -> Board
Creates a new kanban board.

**Parameters:**
- `user_id`: ID of the user creating the board
- `name`: Name of the board

**Returns:** Created Board object

**Example:**
```python
board = kanban.create_board("user123", "My Project")
```

#### get_board(user_id: str, board_id: str) -> Board
Retrieves a board with all its cards organized by columns.

**Parameters:**
- `user_id`: ID of the requesting user
- `board_id`: ID of the board to retrieve

**Returns:** Board object with cards populated in columns

**Raises:** 
- `BoardNotFoundError`: If board doesn't exist
- `PermissionDeniedError`: If user lacks read permission

#### list_boards(user_id: str) -> List[Board]
Lists all boards accessible to the user.

**Parameters:**
- `user_id`: ID of the requesting user

**Returns:** List of Board objects

#### add_card(user_id: str, board_id: str, column: str, title: str, **kwargs) -> Card
Creates a new card in the specified column.

**Parameters:**
- `user_id`: ID of the user creating the card
- `board_id`: ID of the board
- `column`: Name of the column to add the card to
- `title`: Title of the card
- `**kwargs`: Optional parameters:
  - `description`: Card description
  - `assignee`: User ID of assignee
  - `labels`: List of labels
  - `due_date`: Due date (datetime object)
  - `custom_fields`: Dictionary of custom fields

**Returns:** Created Card object

**Raises:**
- `BoardNotFoundError`: If board doesn't exist
- `ColumnNotFoundError`: If column doesn't exist
- `PermissionDeniedError`: If user lacks create permission

#### move_card(user_id: str, board_id: str, card_id: str, to_column: str, position: Optional[int] = None) -> Card
Moves a card to a different column.

**Parameters:**
- `user_id`: ID of the user moving the card
- `board_id`: ID of the board
- `card_id`: ID of the card to move
- `to_column`: Name of the destination column
- `position`: Optional position in the column (default: end)

**Returns:** Updated Card object

**Raises:**
- `CardNotFoundError`: If card doesn't exist
- `ColumnNotFoundError`: If column doesn't exist
- `ValidationError`: If move violates WIP limits

#### update_card(user_id: str, board_id: str, card_id: str, **kwargs) -> Card
Updates card properties.

**Parameters:**
- `user_id`: ID of the user updating the card
- `board_id`: ID of the board
- `card_id`: ID of the card to update
- `**kwargs`: Properties to update (title, description, assignee, labels, etc.)

**Returns:** Updated Card object

#### search_cards(user_id: str, board_id: str, text: Optional[str] = None, labels: Optional[List[str]] = None, assignee: Optional[str] = None) -> List[Card]
Searches for cards matching criteria.

**Parameters:**
- `user_id`: ID of the requesting user
- `board_id`: ID of the board to search
- `text`: Text to search in title and description
- `labels`: Labels that cards must have (AND operation)
- `assignee`: Filter by assignee (empty string for unassigned)

**Returns:** List of matching Card objects

#### add_comment(user_id: str, board_id: str, card_id: str, text: str) -> Comment
Adds a comment to a card.

**Parameters:**
- `user_id`: ID of the user adding the comment
- `board_id`: ID of the board
- `card_id`: ID of the card
- `text`: Comment text

**Returns:** Created Comment object

#### get_board_metrics(user_id: str, board_id: str) -> BoardMetrics
Gets metrics for a board.

**Parameters:**
- `user_id`: ID of the requesting user
- `board_id`: ID of the board

**Returns:** BoardMetrics object with statistics

## KanbanFacade

Advanced facade for custom implementations.

```python
from kanban import KanbanFacade, EventBus

kanban = KanbanFacade(
    repository=custom_repository,
    event_bus=EventBus(),
    permission_checker=custom_permissions,
    search_service=custom_search,
    metrics_calculator=custom_metrics
)
```

### Constructor Parameters

- `repository`: RepositoryInterface implementation (required)
- `event_bus`: EventBus instance (required)
- `permission_checker`: Optional PermissionChecker (default: PermissiveChecker)
- `search_service`: Optional SearchService (default: SimpleSearchService)
- `metrics_calculator`: Optional MetricsCalculator (default: SimpleMetricsCalculator)

The KanbanFacade provides the same methods as SimpleKanban.

## Models

### Board

Represents a kanban board.

**Properties:**
- `id`: Unique identifier
- `name`: Board name
- `owner_id`: ID of the board owner
- `columns`: List of Column objects
- `permissions`: List of Permission objects
- `automation_rules`: List of AutomationRule objects
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp
- `custom_fields`: Dictionary for custom data

**Methods:**

#### get_column(name: str) -> Optional[Column]
Gets a column by name.

#### add_column(name: str, position: Optional[int] = None, wip_limit: Optional[int] = None) -> Column
Adds a new column to the board.

#### remove_column(name: str) -> None
Removes a column from the board.

#### get_all_cards() -> List[Card]
Gets all cards across all columns.

### Card

Represents a card in the kanban board.

**Properties:**
- `id`: Unique identifier
- `board_id`: ID of the containing board
- `column`: Name of the current column
- `position`: Position within the column
- `title`: Card title
- `description`: Optional description
- `assignee`: Optional assignee user ID
- `labels`: List of labels
- `due_date`: Optional due date
- `comments`: List of Comment objects
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp
- `completed_at`: Optional completion timestamp
- `custom_fields`: Dictionary for custom data

**Methods:**

#### add_label(label: str) -> None
Adds a label to the card.

#### remove_label(label: str) -> None
Removes a label from the card.

#### add_comment(author: str, text: str) -> Comment
Adds a comment to the card.

### Column

Represents a column in a kanban board.

**Properties:**
- `name`: Column name
- `position`: Position on the board (0-based)
- `cards`: List of Card objects in the column
- `wip_limit`: Optional work-in-progress limit

**Methods:**

#### add_card(card: Card, position: Optional[int] = None) -> None
Adds a card to the column.

#### remove_card(card_id: str) -> Optional[Card]
Removes and returns a card from the column.

#### is_wip_limit_reached() -> bool
Checks if WIP limit is reached.

### Comment

Represents a comment on a card.

**Properties:**
- `id`: Unique identifier
- `author`: User ID of the comment author
- `text`: Comment text
- `created_at`: Creation timestamp
- `updated_at`: Optional update timestamp

## Repositories

### RepositoryInterface

Abstract base class for implementing custom storage backends.

```python
from kanban.repositories import RepositoryInterface

class MyRepository(RepositoryInterface):
    # Implement all abstract methods
    pass
```

**Required Methods:**

#### Board Operations
- `create_board(board: Board) -> Board`
- `get_board(board_id: str) -> Optional[Board]`
- `update_board(board: Board) -> Board`
- `delete_board(board_id: str) -> None`
- `list_boards(user_id: str) -> List[Board]`

#### Card Operations
- `create_card(card: Card) -> Card`
- `get_card(card_id: str) -> Optional[Card]`
- `update_card(card: Card) -> Card`
- `delete_card(card_id: str) -> None`
- `find_cards(board_id: str, **filters) -> List[Card]`
- `get_cards_by_column(board_id: str, column: str) -> List[Card]`

#### User Operations
- `create_user(user: User) -> User`
- `get_user(user_id: str) -> Optional[User]`

## Events

### EventBus

Manages event subscriptions and publishing.

```python
from kanban.events import EventBus

event_bus = EventBus()
```

**Methods:**

#### subscribe(event_type: str, handler: Union[EventHandler, Callable]) -> None
Subscribes to events.

**Parameters:**
- `event_type`: Event type pattern (supports wildcards: "card.*", "*")
- `handler`: EventHandler instance or callable

**Example:**
```python
def log_event(event):
    print(f"Event: {event.type}")

event_bus.subscribe("card.moved", log_event)
event_bus.subscribe("*", audit_logger)  # All events
```

#### unsubscribe(event_type: str, handler: Union[EventHandler, Callable]) -> None
Unsubscribes from events.

#### publish(event: Event) -> None
Publishes an event to all matching subscribers.

### Event

Represents a system event.

**Properties:**
- `type`: Event type (e.g., "card.created", "board.updated")
- `timestamp`: When the event occurred
- `user_id`: User who triggered the event
- `board_id`: Related board ID (if applicable)
- `data`: Dictionary containing event-specific data

**Event Types:**
- Board events: `board.created`, `board.updated`, `board.deleted`
- Card events: `card.created`, `card.updated`, `card.deleted`, `card.moved`
- Column events: `column.added`, `column.removed`, `column.renamed`
- Comment events: `comment.added`, `comment.updated`, `comment.deleted`
- Label events: `label.added`, `label.removed`
- User events: `user.assigned`, `user.unassigned`

## Permissions

### PermissionChecker

Abstract base class for implementing custom permission systems.

```python
from kanban.permissions import PermissionChecker

class MyPermissions(PermissionChecker):
    def check_permission(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str
    ) -> bool:
        # Your permission logic
        return True
```

**Parameters:**
- `user_id`: ID of the user attempting the action
- `resource_type`: Type of resource ("board", "card", "column", etc.)
- `resource_id`: ID of the specific resource
- `action`: Action being attempted ("create", "read", "update", "delete")

**Returns:** Boolean indicating if permission is granted

## Exceptions

The library defines specific exceptions for different error conditions:

### BoardNotFoundError
Raised when a board cannot be found.

```python
from kanban.exceptions import BoardNotFoundError

try:
    board = kanban.get_board("user", "invalid_id")
except BoardNotFoundError:
    print("Board doesn't exist")
```

### CardNotFoundError
Raised when a card cannot be found.

### ColumnNotFoundError
Raised when a column cannot be found.

### PermissionDeniedError
Raised when a user lacks permission for an operation.

### ValidationError
Raised when data validation fails.

### WIPLimitExceeded
Raised when adding a card would exceed column WIP limit.

## Utility Functions

### create_auto_move_rule(trigger_label: str, target_column: str) -> AutomationRule
Creates a rule that automatically moves cards with a specific label.

**Example:**
```python
from kanban import create_auto_move_rule

rule = create_auto_move_rule("ready-for-review", "In Review")
board.automation_rules.append(rule)
```

### generate_id() -> str
Generates a unique identifier for entities.

**Example:**
```python
from kanban.utils import generate_id

card_id = generate_id()  # Returns UUID string
```

## Type Definitions

The library uses type hints throughout. Key type aliases:

```python
from typing import Dict, List, Optional, Any
from datetime import datetime

BoardId = str
CardId = str
UserId = str
ColumnName = str
Label = str
```

## Thread Safety

The library is designed to be thread-safe when using appropriate repository implementations. The in-memory repository uses threading locks to ensure concurrent access is safe.

## Best Practices

1. **Always handle exceptions**: Wrap operations in try-except blocks
2. **Use type hints**: Leverage the library's type annotations
3. **Subscribe to events**: Use events for logging, notifications, and integrations
4. **Implement proper permissions**: Don't use PermissiveChecker in production
5. **Validate input**: The library validates basic constraints, but add your own business rules

## Version Compatibility

The library follows semantic versioning. The current stable API is version 1.x. Breaking changes will be introduced only in major version updates.