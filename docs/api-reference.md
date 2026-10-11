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
import_board(user_id, data: BoardImport) -> BoardView
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

Import consumes immutable `BoardImport`, `ColumnImport` and `CardImport` values,
exported from `kanban`. It preserves historical IDs and unknown timestamps in
one create-only commit with `IMPORT_BOARD` permission. Existing boards cannot
be overwritten. See [historical import](extending/import.md) and its benchmark.

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
patch_attributes(user_id, board_id, card_id, *, set=None, remove=()) -> CardView
move_card(user_id, board_id, card_id, to_column_id, position=None) -> CardView
delete_card(user_id, board_id, card_id) -> None
block_card(user_id, board_id, card_to_block_id, blocking_card_id) -> None
unblock_card(user_id, board_id, card_to_unblock_id, blocking_card_id) -> None
block_card_external(user_id, board_id, card_id, reason) -> None
unblock_card_external(user_id, board_id, card_id) -> None
search_cards(user_id, board_id, **filters) -> list[CardView]
aging_cards(user_id, board_id, now=None) -> AgingCardsView
aging_card_details(user_id, board_id, now=None) -> AgingCardDetailsView
```

`add_card` and `update_card` accept opaque JSON `attributes`. Updates replace the
whole set. Views and policy/automation contexts expose recursively immutable
copies. See [card attributes](extending/card-attributes.md).
`patch_attributes` sets or removes selected top-level keys inside one transaction.
JSON null is a value; removal is explicit. Ordinary updates retain replacement semantics.

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

`AgingCardDetailsView` returns the same selected cards as immutable `CardAgeView`
rows, each containing `card`, `column`, and calculated `age`. Unknown-age rows
have `age=None`. Its `evaluated_at` captures the single UTC query instant.

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
ColumnPolicyContext
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

Policy contexts carry detached column names, current occupancy and limits from
the transaction board. Move contexts expose `from_column` and `to_column` alongside
IDs. Hosts implement pull gates and exceptions using these facts; core WIP limits
remain enforced. See [workflow policies](extending/workflow-policy.md).
