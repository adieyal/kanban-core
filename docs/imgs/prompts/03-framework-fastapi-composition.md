---
illustration_id: 03
type: framework
style: webcomic-ink
---

FASTAPI COMPOSITION - technical application wiring diagram

LAYOUT: A clean top-to-bottom architecture diagram with generous white space.

TOP: A rounded box labeled "FastAPI routes" with a small HTTP/API icon.

MIDDLE: A prominent teal-highlighted rounded box labeled "KanbanFacade". Draw one solid downward arrow from FastAPI routes to the facade.

BOTTOM: Three separate adapter boxes connected by branching arrows from KanbanFacade: "InMemoryKanbanRepository", "SynchronousKanbanUnitOfWork", and "EventBus". Group them under a subtle label "application-provided adapters".

CONNECTIONS: FastAPI routes call the facade. The facade is the stable business entry point. The three bottom boxes are replaceable infrastructure supplied by the application. Keep arrows clear and non-crossing.

LABELS: FastAPI routes; KanbanFacade; application-provided adapters; InMemoryKanbanRepository; SynchronousKanbanUnitOfWork; EventBus.

COLORS: Pure white background, near-black lines and text, muted teal highlight for KanbanFacade, soft gray for adapter boxes. Do not display hex codes or color names as visible text.

STYLE: Sparse black-ink hand-drawn technical architecture diagram, rounded boxes, slight line wobble, simple API and adapter icons, no realistic or photographic imagery, no clutter. Text must be large, concise, and readable. Do not add labels beyond those specified.

ASPECT: 16:9, presentation-ready, medium complexity.
