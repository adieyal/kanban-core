# Historical board import

Use `KanbanFacade.import_board(user_id, BoardImport(...))` to reconstruct historical
state without replaying creation and movement commands. Hosts translate their own
store records into the public `BoardImport`, `ColumnImport` and `CardImport` inputs.
The library has no knowledge of Fleet, worker jobs, or host storage schemas.

```python
from datetime import timedelta
from kanban import BoardImport, CardImport, ColumnImport

board = kanban.import_board("alice", BoardImport(
    id="queue", name="Queue", owner_id="alice",
    columns=(ColumnImport("review", "Review", max_age=timedelta(hours=1)),),
    cards=(CardImport(
        id="task-1", column_id="review", title="Review patch",
        attributes={"handoff_verified": True},
        created_at=None, entered_column_at=None,
    ),),
))
```

IDs and supplied timestamps are retained. `None` means unknown and stays unknown.
Present timestamps must be timezone-aware. Column input order defines column
positions; card input order defines relative ordering inside each column.
`blocked_by` supplies dependency links; reverse `blocks` links are derived.
External blocks require both a nonempty `blocked_reason` and an aware `blocked_at`.
Input collections and attributes are detached and immutable.

Import validates unique identities and column names, membership, dependency
references and cycles, timestamp/block state, JSON attributes, and WIP group
configuration. Historical occupancy may exceed configured WIP limits: import
records existing work, while subsequent new entries enforce capacity.

Import requires `IMPORT_BOARD` permission. The default permission policy grants it
only to the supplied board owner. Hosts that need another authorization rule
inject a permission policy. Import commits once with `expected_version=0`, so it
cannot replace an existing board or overwrite a concurrent creation.

Import emits one `board.imported` audit event. It does not replay card lifecycle
events, invoke lifecycle workflow policies, or run automation. Import is a separate
historical-state capability; ordinary `add_card` continues to stamp new work with
the injected clock. Future mutations use the usual policies and transaction path.

## Performance target

Run `PYTHONPATH=src .venv/bin/python scripts/benchmark_import.py`. The default workload
imports 100 cards across five columns with nested attributes, dependencies, external
blocks and some unknown entry times, in 20 fresh in-memory repositories. It includes
request construction, validation, snapshots, commit and the returned board view.
External data fetching and host translation are outside this benchmark.

The script reports environment, median, p95 and maximum milliseconds, and exits
unsuccessfully if p95 is not below its default 50 ms target. This is a reproducible
local target rather than a timing guarantee across machines or durable adapters.
