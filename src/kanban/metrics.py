from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol

from .events import CARD_MOVED, Event
from .models import Board, Card

# ============= METRICS =============


class ICalendar(Protocol):
    def working_seconds_between(self, start: datetime, end: datetime) -> int: ...


class TwentyFourSevenCalendar:
    def working_seconds_between(self, start: datetime, end: datetime) -> int:
        return max(0, int((end - start).total_seconds()))


class MetricsCalculator:
    """Calculate kanban metrics"""

    @staticmethod
    def calculate_wip(board: Board) -> dict[str, int]:
        return {col_id: len(col.card_ids) for col_id, col in board.columns.items()}

    @staticmethod
    def calculate_cycle_time(
        card: Card, done_column_ids: set[str], cal: ICalendar
    ) -> int:
        seconds = 0
        for col_id in done_column_ids:
            delta = card.time_in_column.get(col_id)
            if delta:
                start = card.created_at or card.entered_column_at
                if start:
                    end = start + delta
                    seconds += cal.working_seconds_between(start, end)
        return seconds

    @staticmethod
    def calculate_lead_time(
        card: Card, now: datetime, calendar: ICalendar
    ) -> timedelta:
        if not card.created_at:
            return timedelta()
        seconds = calendar.working_seconds_between(card.created_at, now)
        return timedelta(seconds=seconds)

    @staticmethod
    def calculate_throughput(
        events: list[Event],
        done_column_ids: set[str],
        period_days: int = 7,
        now: datetime = None,
    ) -> float:
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(days=period_days)
        completed = 0

        for event in events:
            if (
                event.type == CARD_MOVED
                and event.timestamp > cutoff
                and event.data.get("to_column_id") in done_column_ids
            ):
                completed += 1

        return completed / period_days if period_days > 0 else 0
