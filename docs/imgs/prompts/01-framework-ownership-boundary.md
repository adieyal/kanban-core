---
illustration_id: 01
type: framework
style: webcomic-ink
---

KANBAN-CORE OWNERSHIP AND DEPENDENCY DIRECTION - technical architecture diagram

LAYOUT: A three-layer vertical architecture diagram with a clear top-to-bottom dependency direction and generous white space.

ZONES:
- TOP layer labeled "Application" with three small callers: "HTTP", "Worker", "CLI".
- MIDDLE layer labeled "Kanban Core" containing a bold box "KanbanFacade" and a larger box "Business truth + invariants".
- BOTTOM layer labeled "Outbound ports / detached contexts" with five boxes: "Repository", "Permission policy", "Workflow policy", "Search", "Automation". To the far right add "Event delivery" as a related infrastructure port.

CONNECTIONS: Solid downward arrows from HTTP, Worker, and CLI into KanbanFacade. A strong enclosing boundary around Kanban Core. Arrows from Core to the bottom contracts labeled "facts, snapshots, decisions". At the bottom, show a small infrastructure strip labeled "Application infrastructure implements contracts". Add a coral warning callout outside the core boundary: "extensions do not mutate the aggregate". Add a teal callout inside the core: "one owner of business truth".

LABELS: Application; HTTP; Worker; CLI; Kanban Core; KanbanFacade; Business truth + invariants; Outbound ports / detached contexts; Repository; Permission policy; Workflow policy; Search; Automation; Event delivery; facts, snapshots, decisions; Application infrastructure implements contracts; extensions do not mutate the aggregate; one owner of business truth.

COLORS: Pure white background (#FFFFFF), near-black (#111111) for lines and text, coral (#E8655A) for the warning callout, muted teal (#5FA8A8) for the ownership callout. Color values are rendering guidance only; do not display hex codes or color names as visible text.

STYLE: Sparse black-ink webcomic architecture explainer, hand-drawn rounded boxes, slight line wobble, simple symbolic icons only, no realistic imagery, no clutter. Text should be large, concise, and readable. Clean composition with generous white space. Do not add any labels beyond those specified.

ASPECT: 16:9, presentation-ready, medium complexity.
