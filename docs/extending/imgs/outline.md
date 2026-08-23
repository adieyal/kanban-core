---
type: flowchart
density: minimal
style: webcomic-ink
image_count: 1
---

## Illustration 1

**Position**: docs/extending/persistence.md before the production outbox explanation
**Purpose**: Clarify why the unit of work exists and how it prevents committed state from losing its event.
**Visual Content**: One facade operation produces a snapshot and events, which are committed atomically as database state and outbox record.
**Filename**: 01-flowchart-atomic-outbox-commit.png
