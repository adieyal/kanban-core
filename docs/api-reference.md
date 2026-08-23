# API reference

This is a lookup guide. For a tutorial, start with the [Quickstart](quickstart.md).

## `KanbanFacade`

```python
KanbanFacade(
    repository,
    unit_of_work,
    permission_checker=None,
    searcher=None,
    automation_runner=None,
    clock=None,
    id_factory=None,
    workflow_policy=None,
)
```

### Boards

```text
create_board(user_id, name, columns=None) -> BoardView
get_board(user_id, board_id) -> BoardView
list_boards(user_id) -> list[BoardView]
update_board(user_id, board_id, **changes) -> BoardView
delete_board(user_id, board_id) -> None
```

### Columns

```text
add_column(user_id, board_id, name, position=None) -> ColumnView
update_column(user_id, board_id, column_id, **changes) -> ColumnView
delete_column(user_id, board_id, column_id) -> None
```

### Cards

```text
add_card(user_id, board_id, column_id, title, **fields) -> CardView
update_card(user_id, board_id, card_id, **changes) -> CardView
move_card(user_id, board_id, card_id, to_column_id, position=None) -> CardView
delete_card(user_id, board_id, card_id) -> None
block_card(user_id, board_id, card_to_block_id, blocking_card_id) -> None
unblock_card(user_id, board_id, card_to_unblock_id, blocking_card_id) -> None
search_cards(user_id, board_id, **filters) -> list[CardView]
```

## Views

`BoardView`, `ColumnView` and `CardView` are frozen values. `BoardView` provides:

```python
board.column_named("In Progress")
board.card(card_id)
```

## Public exceptions

```text
KanbanError
ValidationError
NotFoundError
PermissionError
ConcurrencyError
InvalidPersistenceStateError
```

## SPI

Extension/infrastructure code imports from `kanban.spi`:

```text
BoardSnapshot
KanbanRepository
KanbanUnitOfWork
Event
EventPublisher
PermissionContext
PermissionPolicy
CardPolicyContext
CardMovePolicyContext
WorkflowPolicy
SearchCard
SearchContext
CardSearcher
AutomationRunner
AutomationFacts
AutomationCardFacts
AutomationColumnFacts
AutomationAction
MoveCardAction
Clock
IDFactory
```

Internal models and services are not application API.
