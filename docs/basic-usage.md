# Basic Usage Guide

This guide covers the most common use cases for the Kanban Core Library. Most users will find that the `SimpleKanban` class provides everything they need for basic kanban board functionality.

## Getting Started

### Installation

```bash
pip install kanban-core
```

### Creating Your First Board

The simplest way to use the library is through the `SimpleKanban` class:

```python
from kanban import SimpleKanban

# Create a kanban instance
kanban = SimpleKanban()

# Create a board
board = kanban.create_board("user123", "My Project")
print(f"Created board: {board.name} (ID: {board.id})")
```

## Working with Cards

### Adding Cards

```python
# Add cards to the default "To Do" column
card1 = kanban.add_card("user123", board.id, "To Do", "Design the API")
card2 = kanban.add_card("user123", board.id, "To Do", "Write documentation")
card3 = kanban.add_card("user123", board.id, "To Do", "Setup CI/CD pipeline")

# Add a card with more details
card4 = kanban.add_card(
    "user123", 
    board.id, 
    "To Do", 
    "Implement user authentication",
    description="Add OAuth2 support for Google and GitHub",
    assignee="dev456",
    labels=["backend", "security", "priority:high"]
)
```

### Moving Cards Between Columns

```python
# Move a card to "In Progress"
kanban.move_card("user123", board.id, card1.id, "In Progress")

# Move multiple cards
for card_id in [card2.id, card3.id]:
    kanban.move_card("user123", board.id, card_id, "In Progress")
```

### Updating Cards

```python
# Update card details
kanban.update_card(
    "user123", 
    board.id, 
    card1.id,
    title="Design the REST API",
    description="Create OpenAPI specification for all endpoints",
    assignee="designer789"
)

# Add labels to a card
kanban.add_label("user123", board.id, card2.id, "documentation")
kanban.add_label("user123", board.id, card2.id, "high-priority")

# Remove a label
kanban.remove_label("user123", board.id, card2.id, "high-priority")
```

## Board Management

### Listing Boards

```python
# Get all boards for a user
boards = kanban.list_boards("user123")
for board in boards:
    print(f"- {board.name} (ID: {board.id})")
```

### Getting Board Details

```python
# Get a specific board with all its cards
board_data = kanban.get_board("user123", board.id)
print(f"Board: {board_data.name}")
print(f"Columns: {', '.join(col.name for col in board_data.columns)}")
print(f"Total cards: {sum(len(col.cards) for col in board_data.columns)}")

# Print cards by column
for column in board_data.columns:
    print(f"\n{column.name} ({len(column.cards)} cards):")
    for card in column.cards:
        print(f"  - {card.title}")
        if card.assignee:
            print(f"    Assigned to: {card.assignee}")
        if card.labels:
            print(f"    Labels: {', '.join(card.labels)}")
```

### Customizing Columns

```python
# Add a custom column
kanban.add_column("user123", board.id, "Review", position=2)

# Remove a column (cards will be moved to the previous column)
kanban.remove_column("user123", board.id, "Review")

# Rename a column
kanban.rename_column("user123", board.id, "To Do", "Backlog")
```

## Searching and Filtering

### Text Search

```python
# Search cards by text (searches in title and description)
results = kanban.search_cards("user123", board.id, text="API")
for card in results:
    print(f"Found: {card.title} in column {card.column}")
```

### Filter by Labels

```python
# Get all cards with specific label
backend_cards = kanban.search_cards("user123", board.id, labels=["backend"])

# Get cards with multiple labels (AND operation)
urgent_backend = kanban.search_cards(
    "user123", 
    board.id, 
    labels=["backend", "priority:high"]
)
```

### Filter by Assignee

```python
# Get all cards assigned to a specific user
my_cards = kanban.search_cards("user123", board.id, assignee="dev456")

# Get unassigned cards
unassigned = kanban.search_cards("user123", board.id, assignee="")
```

## Working with Comments

```python
# Add a comment to a card
kanban.add_comment(
    "user123", 
    board.id, 
    card1.id, 
    "API design is ready for review"
)

# Get card with comments
card_details = kanban.get_card("user123", board.id, card1.id)
for comment in card_details.comments:
    print(f"{comment.author}: {comment.text}")
    print(f"Posted at: {comment.created_at}")
```

## Basic Metrics

```python
# Get board metrics
metrics = kanban.get_board_metrics("user123", board.id)

print(f"Total cards: {metrics.total_cards}")
print(f"Cards by column:")
for column, count in metrics.cards_by_column.items():
    print(f"  {column}: {count}")

print(f"\nCards by assignee:")
for assignee, count in metrics.cards_by_assignee.items():
    print(f"  {assignee or 'Unassigned'}: {count}")

print(f"\nCards by label:")
for label, count in metrics.cards_by_label.items():
    print(f"  {label}: {count}")
```

## Event Handling

The library emits events for all operations, which you can listen to:

```python
# Create a kanban instance with event handling
kanban = SimpleKanban()

# Define event handlers
def on_card_moved(event):
    print(f"Card moved: {event.data['card_id']} to {event.data['to_column']}")

def on_card_created(event):
    print(f"New card created: {event.data['card'].title}")

# Register handlers
kanban.event_bus.subscribe("card.moved", on_card_moved)
kanban.event_bus.subscribe("card.created", on_card_created)

# Now all operations will trigger events
card = kanban.add_card("user123", board.id, "To Do", "New task")
# Output: New card created: New task

kanban.move_card("user123", board.id, card.id, "In Progress")
# Output: Card moved: <card_id> to In Progress
```

## Error Handling

The library uses specific exceptions for different error conditions:

```python
from kanban.exceptions import (
    BoardNotFoundError,
    CardNotFoundError,
    ColumnNotFoundError,
    PermissionDeniedError,
    ValidationError
)

try:
    # Try to move a card
    kanban.move_card("user123", "invalid_board_id", card.id, "Done")
except BoardNotFoundError:
    print("Board not found!")
except CardNotFoundError:
    print("Card not found!")
except ColumnNotFoundError:
    print("Target column doesn't exist!")
except PermissionDeniedError:
    print("You don't have permission to do that!")
except ValidationError as e:
    print(f"Invalid data: {e}")
```

## Complete Example

Here's a complete example that demonstrates common operations:

```python
from kanban import SimpleKanban
from datetime import datetime

def main():
    # Initialize kanban
    kanban = SimpleKanban()
    
    # Create a project board
    board = kanban.create_board("john_doe", "Website Redesign")
    print(f"Created board: {board.name}")
    
    # Add custom columns
    kanban.add_column("john_doe", board.id, "In Review", position=2)
    kanban.add_column("john_doe", board.id, "Done", position=3)
    
    # Create some tasks
    tasks = [
        ("Design new homepage", "Create mockups and wireframes", "designer", ["design", "frontend"]),
        ("Update color scheme", "Implement new brand colors", "designer", ["design", "branding"]),
        ("Optimize images", "Compress and convert to WebP", "developer", ["performance", "frontend"]),
        ("Write content", "Update all page content", "writer", ["content"]),
        ("Setup analytics", "Implement GA4 tracking", "developer", ["analytics", "backend"]),
    ]
    
    cards = []
    for title, desc, assignee, labels in tasks:
        card = kanban.add_card(
            "john_doe",
            board.id,
            "To Do",
            title,
            description=desc,
            assignee=assignee,
            labels=labels
        )
        cards.append(card)
    
    # Simulate workflow
    # Move first two tasks to In Progress
    kanban.move_card("john_doe", board.id, cards[0].id, "In Progress")
    kanban.move_card("john_doe", board.id, cards[1].id, "In Progress")
    
    # Add a comment to the first card
    kanban.add_comment(
        "john_doe",
        board.id,
        cards[0].id,
        "Initial mockups are ready for review"
    )
    
    # Move first task to review
    kanban.move_card("john_doe", board.id, cards[0].id, "In Review")
    
    # Search for frontend tasks
    frontend_tasks = kanban.search_cards("john_doe", board.id, labels=["frontend"])
    print(f"\nFrontend tasks: {len(frontend_tasks)}")
    for task in frontend_tasks:
        print(f"  - {task.title}")
    
    # Get board overview
    board_data = kanban.get_board("john_doe", board.id)
    print(f"\nBoard Overview:")
    for column in board_data.columns:
        print(f"{column.name}: {len(column.cards)} cards")
    
    # Get metrics
    metrics = kanban.get_board_metrics("john_doe", board.id)
    print(f"\nBoard Metrics:")
    print(f"Total cards: {metrics.total_cards}")
    print(f"By assignee: {dict(metrics.cards_by_assignee)}")

if __name__ == "__main__":
    main()
```

## Next Steps

This guide covers the basic functionality that most users will need. For more advanced use cases, see:

- [Extensibility Guide](extensibility.md) - How to customize and extend the library
- [API Reference](api-reference.md) - Detailed documentation of all classes and methods
- [Examples](examples/) - More complex examples and use cases