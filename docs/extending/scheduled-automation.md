# Scheduled automation

The host schedules calls to `facade.tick(user_id, board_id, max_actions=100)`.
Tick is a transactional command requiring `MANAGE_AUTOMATION`, not a scheduler.
It emits `board.tick` with an injected-clock timestamp. Rules evaluate the usual
automation facts and return supported actions.

All facts evaluated during one tick share its trigger timestamp, even when the
injected clock advances while actions execute.

`TickResult.processed_card_ids` records initial actions attempted, including no-ops.
`deferred_card_ids` records initial actions beyond `max_actions`, in runner order.
The limit is a positive integer and counts actions, so a card may occur more than
once when a runner requests multiple actions for it. Selected actions and their
reactions finish atomically; deferred actions are reevaluated on the next tick.
No continuation or pending command is persisted.

Each selected action has its own 25-event reaction limit. This lets one tick move
more than 25 independent cards while still rejecting automation loops. Invalid
selected actions or looping reactions roll back the complete tick. Normal facade
operations retain their existing automation limit.

Write rules whose successful action removes the match, such as moving an aged card
out of its column or blocking a card only when it is not externally blocked.
Repeated calls then converge. A tick with no actions emits its event without
changing board state or version.
