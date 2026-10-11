# Queue controls implementation

Source: issues #2–#7 and the user's settled contracts in this session.

Change: replacement-only JSON attributes; truthful card timestamps and age queries;
external blocking; grouped WIP limits; bounded transactional automation ticks.
Preserve: dependency blocking APIs, immutable observations, same-operation automation,
workflow validation, WIP enforcement, optimistic concurrency, zero runtime dependencies.
Prove: focused feature and regression tests, lint/format, independent integrated review.

| Unit | Status | Evidence |
| --- | --- | --- |
| Attributes #5 | PASS | 0eab08b; 15 focused attribute tests |
| Timestamps and age #2/#4 | PASS | 4a2f949; 19 age tests including historical records and DST |
| External blocking and grouped WIP #6/#7 | PASS | 9b2b6c6, 92fbc1b; 9 block and 14 group tests |
| Bounded tick #3 | PASS | ee19768; 13 tick tests, including busy boards and cycles |
| Integration and independent review | PASS | Combined queue scenario, two independent final reviews |

Tick batches limit initial requested actions, report deferred card IDs, and complete
selected actions' reactions atomically. Each selected action retains its own bounded
automation chain. Invalid selected actions and cycles fail the complete tick.
Historical missing timestamps remain unknown. Archived cards do not appear in age
queries, but continue to occupy WIP capacity while present in a column.

## Final acceptance

| Requirement | Implementation | Executed evidence |
| --- | --- | --- |
| JSON replacement and immutable observations | attributes.py, card lifecycle, policy/automation contexts | test_card_attributes.py |
| Known lifecycle timestamps; unknown history retained | models, lifecycle, snapshots | test_card_age.py |
| Positive age limits, active cards, elapsed-time ordering | column policy and aging_cards | test_card_age.py including DST and folded-hour ordering |
| Separate idempotent external block and BlockCardAction | facade and shared mutation path | test_external_blocking.py |
| Overlapping WIP groups on creation/entry | Board.validate_group_entry | test_group_wip.py |
| Bounded tick with deferred report and atomic selected actions | transaction loop and TickResult | test_tick.py |
| Queue behavior combines all capabilities | public facade/SPI | test_queue_controls.py |

Final verification: `PYTHONPATH=src .venv/bin/pytest tests/ -q`: 126 passed.
Ruff lint and formatting pass; MyPy passes across 22 source files; import-linter
keeps the adapters-only-SPI contract; `git diff --check` passes.

Independent review corrections: reject unsupported actions before tick bookkeeping;
use one timestamp for block state and event; validate restored lifecycle timestamps;
calculate elapsed ages and order instants in UTC across daylight-saving changes.
Original probes and regression tests pass after correction. No unresolved findings.
Work is local on `feature/queue-controls`; no release, push, or issue closure performed.

# Portable board integration

Source: scoped issues #8–#12, #14–#15 and the user's follow-up contracts.
Prior 2.2.0 implementation is now merged locally into master. Issue #13 is closed
as out of scope. This follow-up runs on `feature/portable-board-integration`.

Change: historical import, policy column/occupancy observations, atomic attribute
patching, blocking documentation, and richer age observations.
Preserve: ordinary creation timestamps, replacement update semantics, immutable
observations, optimistic concurrency and atomic reactions.
Scope: host store translation, worker scheduling, NHW thresholds and bypass rules
remain outside core. No built-in service classes or generic scheduling engine.

| Packet | Status | Evidence |
| --- | --- | --- |
| 1. Import #8/#9 and unknown time #12 | PASS | 50 focused tests; reviewer 79 tests; 100 cards median 28.778 ms, p95 30.678 ms over 20 runs |
| 2. Policy facts #10/#11 | PASS | 27 focused tests; independent review 42 tests; Ruff/MyPy pass |
| 4. Attribute patch and docs #14/#15 | Pending | Pending |
| 3. Rich age observations #12 | Pending | Pending |

Benchmark host: Intel Core Ultra 7 165U, Python 3.13.3, Linux x86_64.
Import is create-only, checked with IMPORT_BOARD permission and expected version
zero. It emits one import audit event without replaying historical commands.
Historical overcapacity is retained; subsequent entries enforce WIP limits.
