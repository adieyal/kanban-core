from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

# ============= TYPE ALIASES & EXCEPTIONS =============

Validator = Callable[[Any], None]


class KanbanError(Exception):
    """Base exception for all library errors."""


class ValidationError(KanbanError):
    """For business rule violations."""


class PermissionError(KanbanError):
    """For authorization failures."""


class NotFoundError(KanbanError):
    """For when an entity cannot be found."""


class ConcurrencyError(KanbanError):
    """For optimistic locking failures (lost updates)."""


class InvalidPersistenceStateError(KanbanError):
    """Persisted state violates business-module invariants."""


@runtime_checkable
class Clock(Protocol):
    def __call__(self) -> datetime: ...


def utc_clock() -> datetime:
    return datetime.now(timezone.utc)


@runtime_checkable
class IDFactory(Protocol):
    def __call__(self) -> str: ...


def uuid4_factory() -> str:
    return str(uuid.uuid4())
