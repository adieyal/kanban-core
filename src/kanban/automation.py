from __future__ import annotations

from .events import Event
from .exceptions import ValidationError
from .models import AutomationRule, Board
from .services import AutomationContext, _KanbanServiceCore

# ============= EXAMPLE AUTOMATION RULES =============


def create_auto_move_rule(from_label: str, to_column_name: str) -> AutomationRule:
    def trigger(event: Event) -> bool:
        return event.type == "card.updated" and "custom_fields" in event.data

    # Updated signature to include service_core and context
    def action(
        event: Event,
        board: Board,
        service_core: _KanbanServiceCore,
        context: AutomationContext,
    ):
        card = board.cards.get(event.entity_id)
        # Check for the label in custom_fields
        if card and from_label in card.custom_fields.get("labels", set()):
            if col := next(
                (c for c in board.columns.values() if c.name == to_column_name), None
            ):
                if card.column_id != col.id:
                    try:
                        # Assuming _internal_move is a helper function to move the card
                        service_core._internal_move(board, card.id, col.id)
                    except ValidationError:
                        pass

    return AutomationRule(
        id=f"auto-move-{from_label}-to-{to_column_name}",
        name=f"Auto-move '{from_label}' to {to_column_name}",
        trigger=trigger,
        action=action,
    )


def create_due_date_warning_rule(days_before: int = 3) -> AutomationRule:
    def trigger(event: Event) -> bool:
        return event.type in ["card.created", "card.updated"]

    # Use the new, correct signature
    def action(
        event: Event,
        board: Board,
        service_core: _KanbanServiceCore,
        context: AutomationContext,
    ):
        card = board.cards.get(event.entity_id)
        if card and card.due_date and not card.archived:
            # Use the injected clock from the service core
            days_until = (card.due_date.date() - service_core.clock().date()).days

            # Get labels from custom_fields, providing a default empty set
            labels = card.custom_fields.get("labels", set()).copy()
            label_to_add = "due-soon"

            # Directly mutate the board state
            if days_until <= days_before and label_to_add not in labels:
                labels.add(label_to_add)
                card.custom_fields["labels"] = labels
                card.updated_at = (
                    service_core.clock()
                )  # Good practice to update timestamp
            elif days_until > days_before and label_to_add in labels:
                labels.remove(label_to_add)
                card.custom_fields["labels"] = labels
                card.updated_at = service_core.clock()

    return AutomationRule(
        id=f"due-date-warning-{days_before}-days",
        name=f"Due date warning ({days_before} days)",
        trigger=trigger,
        action=action,
    )
