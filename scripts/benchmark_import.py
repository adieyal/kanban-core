"""Benchmark public import, including request construction, validation and commit."""

from __future__ import annotations

import argparse
import json
import math
import platform
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter

from kanban import BoardImport, CardImport, ColumnImport, KanbanFacade
from kanban_adapters import (
    EventBus,
    InMemoryKanbanRepository,
    SynchronousKanbanUnitOfWork,
)


def import_once(count: int) -> float:
    started = perf_counter()
    repository = InMemoryKanbanRepository()
    facade = KanbanFacade(
        repository, SynchronousKanbanUnitOfWork(repository, EventBus())
    )
    historical = datetime(2020, 1, 1, tzinfo=timezone.utc)
    columns = tuple(
        ColumnImport(f"column-{i}", f"Stage {i}", max_age=timedelta(hours=1))
        for i in range(5)
    )
    cards = tuple(
        CardImport(
            id=f"card-{i}",
            column_id=columns[i % len(columns)].id,
            title=f"Task {i}",
            attributes={
                "review": {"verdict": "pending", "evidence": ["tests", "handoff"]},
                "attempt": i,
            },
            blocked_by=frozenset({f"card-{i - 1}"})
            if i and i % 3 == 0
            else frozenset(),
            created_at=historical,
            entered_column_at=historical if i % 10 else None,
            blocked_reason="Awaiting input" if i % 4 == 0 else None,
            blocked_at=historical if i % 4 == 0 else None,
        )
        for i in range(count)
    )
    board = facade.import_board(
        "owner", BoardImport("history", "History", "owner", columns, cards)
    )
    assert len(board.cards) == count
    return (perf_counter() - started) * 1000


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cards", type=int, default=100)
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--max-ms", type=float, default=50)
    args = parser.parse_args()
    if args.cards <= 0 or args.iterations <= 0 or args.max_ms <= 0:
        parser.error("Counts and target must be positive")
    timings = [import_once(args.cards) for _ in range(args.iterations)]
    p95 = sorted(timings)[math.ceil(len(timings) * 0.95) - 1]
    cpu_lines = Path("/proc/cpuinfo").read_text().splitlines()
    cpu = next(
        (
            line.split(":", 1)[1].strip()
            for line in cpu_lines
            if line.startswith("model name")
        ),
        platform.machine(),
    )
    print(
        json.dumps(
            {
                "cards": args.cards,
                "iterations": args.iterations,
                "median_ms": round(statistics.median(timings), 3),
                "p95_ms": round(p95, 3),
                "max_ms": round(max(timings), 3),
                "target_ms": args.max_ms,
                "target_met": p95 < args.max_ms,
                "python": platform.python_version(),
                "platform": platform.platform(),
                "cpu": cpu,
            },
            indent=2,
        )
    )
    if p95 >= args.max_ms:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
