"""Automation runner interfaces and implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ..events import Event
from ..exceptions import KanbanError
from ..models import Board
from ..repositories import snapshot_board
from .automation_types import AutomationContext

if TYPE_CHECKING:
    from .core import _KanbanServiceCore


class IAutomationRunner(ABC):
    """Interface for pluggable automation execution strategies."""

    @abstractmethod
    def run(
        self,
        board: Board,
        event: Event,
        service_core: _KanbanServiceCore,
        ctx: AutomationContext,
    ) -> bool:
        """
        Execute automation rules.
        Returns a boolean 'dirty' flag indicating if the board was modified.
        """
        pass


class SyncAutomationRunner(IAutomationRunner):
    """Synchronous automation runner with chain limit protection."""

    MAX_CHAIN = 25  # sane default

    def run(
        self,
        board: Board,
        event: Event,
        service_core: _KanbanServiceCore,
        ctx: AutomationContext,
    ) -> bool:
        if len(ctx.processed_event_ids) >= self.MAX_CHAIN:
            raise KanbanError("Automation chain limit exceeded")

        if event.id in ctx.processed_event_ids:
            return False
        ctx.processed_event_ids.add(event.id)

        dirty = False
        for rule in filter(
            lambda r: r.enabled and r.trigger(event), board.automation_rules
        ):
            before = snapshot_board(board)
            rule.action(event, board, service_core, ctx)
            dirty |= board != before
        return dirty
