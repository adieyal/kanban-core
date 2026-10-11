# External blocking

`block_card_external(user_id, board_id, card_id, reason)` records a nonempty
external reason and the injected clock time. `unblock_card_external(...)`
clears only that external block. Existing `block_card` and `unblock_card`
continue to manage card dependencies.

Card views, workflow policy contexts, and automation facts expose
`blocked_reason`, `blocked_at`, and `is_blocked`. A card is blocked if either an
external reason or dependency remains. Policies validate external block changes
through `validate_update`.

External block changes emit `card.externally_blocked` or
`card.externally_unblocked`, with the new or cleared `reason`. Repeating the same
reason or clearing an already clear block changes neither state nor events.
`kanban.spi.BlockCardAction(card_id, reason)` uses the same mutation and policy
path inside the triggering transaction; any rejected action rolls back the
entire transaction.

# Shared WIP groups

Configure a board with `update_board(user_id, board_id,
wip_groups=[WipGroup("Active", (doing_id, review_id), 4)])`. This replaces the
whole group configuration; pass `[]` to remove it. `WipGroup` is exported from
`kanban`, and board views expose immutable `wip_groups`.

A group needs a unique nonempty name, distinct existing column IDs, and a
positive integer limit. All overlapping groups enforce their capacities on
creation and entry from outside the group, including automated moves. Movement
between group members remains permitted at capacity. Capacity counts all cards
occupying those columns, including archived cards, consistently with individual
column limits.

Lowering a limit below occupancy is allowed; further entries wait for occupancy
to drop. Remove a column from all groups before deleting it. Configuration and
card mutations use the existing optimistic transaction path, so concurrent
writes cannot silently overfill capacity. Historical snapshots have no groups;
restoring invalid group configuration fails explicitly.
