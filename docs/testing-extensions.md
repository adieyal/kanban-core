# Testing extensions

Test both the extension contract and the business boundary.

## Persistence

Test round trips, optimistic concurrency, delete version checks and malformed
persisted state. Adapters should store/return `BoardSnapshot`, not mutable domain
objects.

## Policies

Test permission/workflow implementations using detached contexts, then add one
facade-level integration test proving the policy is enforced.

## Search

Verify returned IDs belong to the supplied `SearchContext` and search does not
mutate Kanban state.

## Automation

Test rules against immutable facts, then add a facade-level test proving requested
actions still pass through normal business validation.

## Determinism

Inject a fixed `Clock` and deterministic `IDFactory` when assertions depend on time
or generated IDs.
