---
illustration_id: 02
type: comparison
style: webcomic-ink
---

REPOSITORY VS UNIT OF WORK - technical comparison diagram

LAYOUT: A clean two-column comparison with generous white space. Left column explains reading current state; right column explains committing one business operation. Use a shared lower outcome row.

LEFT COLUMN: Heading "read current state". A downward arrow to a rounded box labeled "KanbanRepository". Below it, a document icon labeled "BoardSnapshot". Add a small caption "load and list persisted state".

RIGHT COLUMN: Heading "commit one business operation". A downward arrow to a rounded box labeled "KanbanUnitOfWork". From it, split into two arrows to two sibling boxes labeled "BoardSnapshot" and "Events". Add a small caption "make resulting state and events durable together".

CONNECTIONS: Keep the two columns visually separate. Make the right column's split explicit: one operation enters the unit of work, then produces both the resulting BoardSnapshot and Events. Use a subtle teal highlight around the unit-of-work column to show its commit boundary.

LABELS: read current state; commit one business operation; KanbanRepository; KanbanUnitOfWork; BoardSnapshot; Events; load and list persisted state; make resulting state and events durable together.

COLORS: Pure white background (#FFFFFF), near-black (#111111) for lines and text, muted teal (#5FA8A8) for the unit-of-work boundary, soft gray for the repository side. Color values are rendering guidance only; do not display hex codes or color names as visible text.

STYLE: Sparse black-ink hand-drawn technical comparison, rounded boxes, slight line wobble, simple document icons, no realistic or photographic imagery, no clutter. Text must be large, concise, and readable. Do not add labels beyond those specified.

ASPECT: 16:9, presentation-ready, medium complexity.
