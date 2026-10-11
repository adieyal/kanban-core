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
tick(user_id, board_id, *, max_actions=100) -> TickResult
```

`update_board(..., wip_groups=[WipGroup(name, column_ids, limit)])` replaces the
board's shared capacity groups. Import `WipGroup` from `kanban`. Groups may
overlap; every applicable limit is checked on creation and entry. Moves inside
a group retain capacity. Cards in columns count toward WIP even when archived.
Tick requires `MANAGE_AUTOMATION`; its result reports processed and deferred
initial action card IDs. See [scheduled automation](extending/scheduled-automation.md).

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
block_card_external(user_id, board_id, card_id, reason) -> None
unblock_card_external(user_id, board_id, card_id) -> None
search_cards(user_id, board_id, **filters) -> list[CardView]
aging_cards(user_id, board_id, now=None) -> AgingCardsView
```

`add_card` and `update_card` accept opaque JSON `attributes`. Updates replace the
whole set. Views and policy/automation contexts expose recursively immutable
copies. See [card attributes](extending/card-attributes.md).

External blocking has a nonempty reason and is independent of dependency
blocking. Repeating the same block is a no-op. See
[blocking and shared WIP](extending/blocking-and-wip.md).

## Views

`BoardView`, `ColumnView` and `CardView` are frozen values. `BoardView` provides:

```python
board.column_named("In Progress")
board.card(card_id)
```

`CardView` also exposes `attributes`, `created_at`, `entered_column_at`,
`blocked_reason`, `blocked_at`, and `is_blocked`. Historical lifecycle timestamps
may be `None`. `ColumnView.max_age` is an optional positive `timedelta` configured
through `update_column(..., policy={"max_age": ...})`.

`AgingCardsView.cards` contains unarchived cards strictly past their column limit,
ordered by elapsed time in the current column. `unknown_age_cards` contains
unarchived cards in age-limited columns without a known entry timestamp.
Queries accept timezone-aware `now` or use the injected clock. See
[card age](extending/card-age.md).

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
BlockCardAction
Clock
IDFactory
```

Internal models and services are not application API.
