from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from kanban import KanbanError, KanbanFacade, ValidationError
from kanban_adapters import (
    EventBus,
    InMemoryKanbanRepository,
    SynchronousKanbanUnitOfWork,
)

DEMO_USER = "demo-user"
HERE = Path(__file__).resolve().parent

repository = InMemoryKanbanRepository()
events = EventBus(max_size=250)
unit_of_work = SynchronousKanbanUnitOfWork(repository, events)
kanban = KanbanFacade(repository, unit_of_work)

app = FastAPI(title="Kanban Core Demo", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")

_seeded = False


def _ensure_seed_data() -> str:
    global _seeded
    boards = kanban.list_boards(DEMO_USER)
    if boards:
        _seeded = True
        return boards[0].id

    board = kanban.create_board(
        DEMO_USER,
        "Product launch",
        ["Backlog", "In Progress", "Review", "Done"],
    )

    backlog = board.column_named("Backlog")
    progress = board.column_named("In Progress")
    review = board.column_named("Review")
    assert backlog is not None and progress is not None and review is not None

    kanban.update_column(
        DEMO_USER,
        board.id,
        progress.id,
        policy={"wip_limit": 3},
    )

    kanban.add_card(
        DEMO_USER,
        board.id,
        backlog.id,
        "Write launch announcement",
        description="Draft the release post and collect screenshots.",
        assignee_ids={"Maya"},
        size=2,
    )
    kanban.add_card(
        DEMO_USER,
        board.id,
        backlog.id,
        "Polish onboarding flow",
        description="Tighten the first-run experience before launch.",
        assignee_ids={"Sam"},
        size=5,
    )
    kanban.add_card(
        DEMO_USER,
        board.id,
        progress.id,
        "Final QA pass",
        description="Exercise the critical launch paths on staging.",
        assignee_ids={"Noah"},
        size=3,
    )
    kanban.add_card(
        DEMO_USER,
        board.id,
        review.id,
        "Release notes",
        description="Make sure every user-visible change is represented.",
        assignee_ids={"Maya"},
        size=1,
    )

    _seeded = True
    return board.id


def _current_board(board_id: str | None):
    boards = kanban.list_boards(DEMO_USER)
    if not boards:
        board_id = _ensure_seed_data()
        boards = kanban.list_boards(DEMO_USER)

    selected = next((board for board in boards if board.id == board_id), None)
    if selected is None:
        selected = boards[0]
    return selected, boards


def _recent_events(limit: int = 18) -> list[dict[str, object]]:
    history = events.get_events()
    rendered: list[dict[str, object]] = []
    for event in reversed(history[-limit:]):
        rendered.append(
            {
                "id": event.id,
                "type": event.type,
                "entity_type": event.entity_type,
                "entity_id": event.entity_id,
                "time": event.timestamp.strftime("%H:%M:%S"),
                "version": event.aggregate_version,
                "data": event.data,
            }
        )
    return rendered


def _context(request: Request, board_id: str | None, error: str | None = None):
    board, boards = _current_board(board_id)
    return {
        "request": request,
        "board": board,
        "boards": boards,
        "events": _recent_events(),
        "error": error,
        "demo_user": DEMO_USER,
    }


def _redirect_to_board(board_id: str, error: str | None = None):
    target = f"/?board_id={board_id}"
    if error:
        from urllib.parse import quote

        target += f"&error={quote(error)}"
    return RedirectResponse(target, status_code=303)


@app.on_event("startup")
def seed_demo() -> None:
    _ensure_seed_data()


@app.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    board_id: str | None = None,
    error: str | None = None,
):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context=_context(request, board_id, error),
    )


@app.get("/fragments/events", response_class=HTMLResponse)
def event_fragment(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="_events.html",
        context={"events": _recent_events()},
    )


@app.post("/boards")
def create_board(
    name: Annotated[str, Form()],
):
    try:
        board = kanban.create_board(DEMO_USER, name)
        return _redirect_to_board(board.id)
    except KanbanError as exc:
        current, _ = _current_board(None)
        return _redirect_to_board(current.id, str(exc))


@app.post("/boards/{board_id}/columns")
def create_column(
    board_id: str,
    name: Annotated[str, Form()],
):
    try:
        kanban.add_column(DEMO_USER, board_id, name)
        return _redirect_to_board(board_id)
    except KanbanError as exc:
        return _redirect_to_board(board_id, str(exc))


@app.post("/boards/{board_id}/columns/{column_id}")
def update_column(
    board_id: str,
    column_id: str,
    name: Annotated[str, Form()],
    wip_limit: Annotated[str, Form()] = "",
):
    try:
        limit: int | None = None
        if wip_limit.strip():
            limit = int(wip_limit)
            if limit < 1:
                raise ValidationError("WIP limit must be at least 1")

        kanban.update_column(
            DEMO_USER,
            board_id,
            column_id,
            name=name,
            policy={"wip_limit": limit},
        )
        return _redirect_to_board(board_id)
    except (KanbanError, ValueError) as exc:
        return _redirect_to_board(board_id, str(exc))


@app.post("/boards/{board_id}/columns/{column_id}/delete")
def delete_column(board_id: str, column_id: str):
    try:
        kanban.delete_column(DEMO_USER, board_id, column_id)
        return _redirect_to_board(board_id)
    except KanbanError as exc:
        return _redirect_to_board(board_id, str(exc))


@app.post("/boards/{board_id}/cards")
def create_card(
    board_id: str,
    column_id: Annotated[str, Form()],
    title: Annotated[str, Form()],
    description: Annotated[str, Form()] = "",
    assignees: Annotated[str, Form()] = "",
    size: Annotated[str, Form()] = "",
):
    try:
        fields: dict[str, object] = {
            "description": description.strip(),
            "assignee_ids": {
                item.strip() for item in assignees.split(",") if item.strip()
            },
        }
        if size.strip():
            fields["size"] = float(size)

        kanban.add_card(
            DEMO_USER,
            board_id,
            column_id,
            title,
            **fields,
        )
        return _redirect_to_board(board_id)
    except (KanbanError, ValueError) as exc:
        return _redirect_to_board(board_id, str(exc))


@app.post("/boards/{board_id}/cards/{card_id}")
def update_card(
    board_id: str,
    card_id: str,
    title: Annotated[str, Form()],
    description: Annotated[str, Form()] = "",
    assignees: Annotated[str, Form()] = "",
    size: Annotated[str, Form()] = "",
    archived: Annotated[str | None, Form()] = None,
):
    try:
        changes: dict[str, object] = {
            "title": title,
            "description": description.strip(),
            "assignee_ids": {
                item.strip() for item in assignees.split(",") if item.strip()
            },
            "archived": archived == "on",
            "size": float(size) if size.strip() else None,
        }
        kanban.update_card(DEMO_USER, board_id, card_id, **changes)
        return _redirect_to_board(board_id)
    except (KanbanError, ValueError) as exc:
        return _redirect_to_board(board_id, str(exc))


@app.post("/boards/{board_id}/cards/{card_id}/delete")
def delete_card(board_id: str, card_id: str):
    try:
        kanban.delete_card(DEMO_USER, board_id, card_id)
        return _redirect_to_board(board_id)
    except KanbanError as exc:
        return _redirect_to_board(board_id, str(exc))


@app.post("/boards/{board_id}/cards/{card_id}/move")
def move_card(
    board_id: str,
    card_id: str,
    to_column_id: Annotated[str, Form()],
    position: Annotated[int, Form()],
):
    try:
        kanban.move_card(
            DEMO_USER,
            board_id,
            card_id,
            to_column_id,
            position,
        )
        return JSONResponse({"ok": True})
    except KanbanError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=409)


@app.post("/boards/{board_id}/cards/{card_id}/block")
def block_card(
    board_id: str,
    card_id: str,
    blocking_card_id: Annotated[str, Form()],
):
    try:
        kanban.block_card(
            DEMO_USER,
            board_id,
            card_id,
            blocking_card_id,
        )
        return _redirect_to_board(board_id)
    except KanbanError as exc:
        return _redirect_to_board(board_id, str(exc))


@app.post("/boards/{board_id}/cards/{card_id}/unblock")
def unblock_card(
    board_id: str,
    card_id: str,
    blocking_card_id: Annotated[str, Form()],
):
    try:
        kanban.unblock_card(
            DEMO_USER,
            board_id,
            card_id,
            blocking_card_id,
        )
        return _redirect_to_board(board_id)
    except KanbanError as exc:
        return _redirect_to_board(board_id, str(exc))
