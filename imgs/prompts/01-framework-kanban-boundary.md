---
illustration_id: 01
type: framework
style: webcomic-ink
---

KANBAN-CORE SYSTEM BOUNDARY - technical architecture diagram

LAYOUT: A clean left-to-right architecture diagram with three large zones and generous white space. Use short, highly legible labels only.

ZONES:
- LEFT zone: a simple application/browser icon labeled "Your application" and a small note "controllers, jobs, CLI".
- CENTER zone: a bold rounded box labeled "KanbanFacade" above a larger bounded box labeled "Kanban business module". Inside the bounded box, show small labels "state", "invariants", "workflow".
- RIGHT zone: four separate adapter boxes labeled "Repository", "Policies", "Search + automation", and "Events / outbox", grouped under "Infrastructure".

CONNECTIONS: Solid arrows from Your application to KanbanFacade and from KanbanFacade into the business module. Dashed outbound arrows from the business module to the four infrastructure contracts. Add a small coral callout near the center: "one business entry point". Add a small teal callout near the right: "replaceable adapters".

LABELS: Your application; controllers, jobs, CLI; KanbanFacade; Kanban business module; state; invariants; workflow; Infrastructure; Repository; Policies; Search + automation; Events / outbox; one business entry point; replaceable adapters.

COLORS: Pure white background (#FFFFFF), near-black (#111111) for all lines and text, coral (#E8655A) for the single boundary callout, muted teal (#5FA8A8) for the adapter callout. Color values are rendering guidance only; do not display hex codes or color names as visible text.

STYLE: Sparse black-ink webcomic technical diagram, loose hand-drawn lines, slight wobble, simple icons, no realistic or photographic imagery, no decorative clutter. Text should be large, concise, and readable. Clean composition with generous white space. Do not add any labels beyond those specified.

ASPECT: 16:9, presentation-ready, medium complexity.
