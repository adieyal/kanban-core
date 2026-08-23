# Integration patterns

Composition belongs at the application edge. Framework code calls the facade;
infrastructure implements SPI contracts.

## Application factory

```python
def make_kanban() -> KanbanFacade:
    return KanbanFacade(
        PostgresKanbanRepository(...),
        PostgresKanbanUnitOfWork(...),
        permission_checker=ApplicationPermissionPolicy(...),
    )
```

## Web request

```python
def move_card_view(request, board_id, card_id):
    kanban = make_kanban()
    kanban.move_card(
        str(request.user.id),
        board_id,
        card_id,
        request.POST["to_column_id"],
    )
```

Authentication remains outside Kanban Core.

## Worker

```python
def process_work_item(user_id, board_id, card_id, column_id):
    make_kanban().move_card(user_id, board_id, card_id, column_id)
```

## CLI / management command

```python
def main():
    board = make_kanban().create_board("operator", "Migration board")
    print(board.id)
```

The framework knows how to compose Kanban Core. Kanban Core does not know which
framework hosts it.

## Included demo

The repository's [`kanban-demo-ui`](../kanban-demo-ui/) is a concrete FastAPI
composition example. Its routes call `KanbanFacade`; the in-memory repository,
synchronous unit of work and event bus are supplied at the application edge.

![FastAPI composition: routes call KanbanFacade, which is wired to replaceable application-provided adapters](imgs/03-framework-fastapi-composition.png)

The browser's native drag-and-drop interaction is only presentation behavior. It
requests a move from the server, where Kanban Core applies the normal WIP, workflow,
ordering, transaction and event rules. This keeps the example useful without making
the UI a second owner of business behavior.
