# Card age and column limits

Cards expose `created_at` and `entered_column_at` in views and automation facts.
Creation sets both to the injected clock's timestamp. Moving between columns
resets `entered_column_at`; reordering, updating and no-op moves preserve it.
Creation and move events use the same timestamp as the corresponding state.
Snapshots persist both timestamps. Historic snapshots without them restore to
`None`, meaning unknown, rather than inventing dates.

Set an optional positive `datetime.timedelta` age limit with
`facade.update_column(user_id, board_id, column_id, policy={"max_age": limit})`.
Setting `max_age` to `None` clears the limit. Column views and automation facts
expose it. This is a monitoring limit: exceeding it does not prohibit movement.

`facade.aging_cards(user_id, board_id, now=None)` checks view permission and returns
an immutable `AgingCardsView`. Its `cards` tuple includes active cards strictly
past their current column's age limit, sorted by column-entry timestamp and then
card ID. `unknown_age_cards` contains active cards in limited columns with an
unknown entry timestamp, sorted by ID. Archived cards and columns without age
limits are excluded. The query uses the injected clock when `now` is omitted,
emits no events and writes no state. Clocks and explicit query times must return
or contain timezone-aware datetimes. Present timestamps in persisted cards must
also be timezone-aware; invalid records fail during restore. Queries measure
elapsed time and order instants in UTC across daylight-saving changes.
A host scheduler can query age limits without an automation tick.
