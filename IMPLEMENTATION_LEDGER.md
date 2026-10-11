# Queue controls implementation

Source: issues #2–#7 and the user's settled contracts in this session.

Change: replacement-only JSON attributes; truthful card timestamps and age queries;
external blocking; grouped WIP limits; bounded transactional automation ticks.
Preserve: dependency blocking APIs, immutable observations, same-operation automation,
workflow validation, WIP enforcement, optimistic concurrency, zero runtime dependencies.
Prove: focused feature and regression tests, lint/format, independent integrated review.

| Unit | Status | Evidence |
| --- | --- | --- |
| Attributes #5 | Active in isolated worktree | Pending |
| Timestamps and age #2/#4 | Active in isolated worktree | Pending |
| External blocking and grouped WIP #6/#7 | Active in isolated worktree | Pending |
| Bounded tick #3 | Active locally | Pending |
| Integration and independent review | Pending | Pending |

Tick batches limit initial requested actions, report deferred card IDs, and complete
selected actions' reactions atomically. Each selected action retains its own bounded
automation chain. Invalid selected actions and cycles fail the complete tick.
Historical missing timestamps remain unknown. Archived cards do not appear in age
queries, but continue to occupy WIP capacity while present in a column.
