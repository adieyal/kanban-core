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
