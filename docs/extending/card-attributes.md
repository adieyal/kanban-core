# Card attributes

Cards carry an opaque JSON object for host-specific facts such as handoffs and
review verdicts. The core validates its representation but does not interpret
its keys. Workflow policies and automation runners receive the same attributes
as the public card view, so they can make decisions without a host lookup.

```python
card = kanban.add_card(
    "alice", board_id, todo_id, "Review patch",
    attributes={"review": {"verdict": "pending"}, "handoffs": ["worker-1"]},
)

kanban.update_card(
    "alice", board_id, card.id,
    attributes={"review": {"verdict": "accepted"}},
)
```

An update replaces the entire attribute object. In this example it removes
`handoffs`. Omit `attributes` to retain the current object, or pass `{}` to clear
it. A caller can construct a replacement from `card.attributes`, including its
nested read-only values. Read-then-write merges can overwrite concurrent host
updates, so a host that needs concurrency protection must coordinate those
operations.

Allowed values are strings, booleans, integers, finite floats, null, arrays and
objects with string keys. Mapping and tuple inputs are accepted and normalized
to dictionaries and lists. Sets, datetimes, arbitrary objects, non-string keys,
non-finite numbers and cycles raise `ValidationError`. The core copies inputs,
so later caller mutations do not alter a card or its event history.

`CardView.attributes`, `CardPolicyContext.attributes` and
`AutomationCardFacts.attributes` are detached and recursively immutable.
Objects become read-only mappings and arrays become tuples. Policies see the
proposed attributes during creation and update, and the current attributes
during movement and deletion. A policy rejection rolls back the operation.

Snapshots preserve nested JSON object and array shapes. Snapshots written
before attributes existed restore with an empty object. Card creation and
update events include attributes in their normal `after` and `before` payloads.

## Transactional patches

Use `patch_attributes` to change selected top-level keys inside one operation:

```python
kanban.patch_attributes(
    "alice", board_id, card.id,
    set={"review": {"verdict": "accepted"}, "note": None},
    remove=["temporary"],
)
```

Unmentioned keys stay unchanged. Each supplied value replaces the whole value
at that key, including nested objects. `None` is JSON null; deletion is explicit
through `remove`. Setting and removing the same key is rejected. Removing an
absent key is harmless; repeated identical and empty patches are no-ops.

Patches use `EDIT_CARD`, validate the resulting attributes through the workflow
policy, and produce the usual `card.updated` before/after event. Automation runs
inside the same transaction. Rejected policies, invalid actions and conflicting
repository writes fail without committing the patch or its events.

Atomicity covers the configured repository and unit of work. A host that rebuilds
an in-memory board and separately writes an external store must enforce matching
concurrency and transaction semantics in that store; the library cannot protect
writes performed outside its unit of work.
