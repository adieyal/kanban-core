"""Automation type definitions to avoid circular imports."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AutomationContext:
    """Context for automation execution tracking."""

    processed_event_ids: set[str] = field(default_factory=set)
