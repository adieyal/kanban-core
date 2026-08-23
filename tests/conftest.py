"""Pytest configuration and shared fixtures."""

import pytest

from kanban import KanbanFacade
from kanban_adapters import (
    EventBus,
    InMemoryKanbanRepository,
    SynchronousKanbanUnitOfWork,
)


@pytest.fixture
def kanban() -> KanbanFacade:
    repository = InMemoryKanbanRepository()
    return KanbanFacade(repository, SynchronousKanbanUnitOfWork(repository, EventBus()))
