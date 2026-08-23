---
illustration_id: 01
type: flowchart
style: webcomic-ink
---

ATOMIC STATE AND EVENT COMMIT - technical process flowchart

LAYOUT: A left-to-right process flow with five stages, generous white space, and a clearly emphasized single transaction boundary around the final two writes.

STEPS:
1. "Facade operation" - a simple command icon labeled "move card".
2. "New BoardSnapshot" - immutable state record.
3. "Events" - one or more business events.
4. "KanbanUnitOfWork" - commit coordinator.
5. Inside one large outlined transaction box: two parallel destinations, "database state" and "outbox record".

CONNECTIONS: Arrow from Facade operation splitting into New BoardSnapshot and Events. Both arrows converge on KanbanUnitOfWork. Arrow from the coordinator into a large transaction boundary labeled "one transaction". Inside it, arrows branch to database state and outbox record. Add a small coral crossed-out note below the flow: "save, then publish" with "failure gap". Add a teal note below the transaction: "state + event durable together".

LABELS: Facade operation; move card; New BoardSnapshot; Events; KanbanUnitOfWork; one transaction; database state; outbox record; save, then publish; failure gap; state + event durable together.

COLORS: Pure white background (#FFFFFF), near-black (#111111) for all lines and text, coral (#E8655A) for the failure-gap warning, muted teal (#5FA8A8) for the successful atomic outcome. Color values are rendering guidance only; do not display hex codes or color names as visible text.

STYLE: Sparse black-ink hand-drawn technical flowchart, rounded stage boxes, wobbly arrows, simple document and database icons, no realistic or photographic imagery, no clutter. Text should be large, concise, and readable. Clean composition with generous white space. Do not add any labels beyond those specified.

ASPECT: 16:9, presentation-ready, medium complexity.
