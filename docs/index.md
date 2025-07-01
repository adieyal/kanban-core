# Kanban Core Library Documentation

Welcome to the comprehensive documentation for the Kanban Core Library - a flexible, extensible kanban board implementation for Python applications.

## Quick Navigation

### 🚀 Getting Started
- **[Basic Usage Guide](basic-usage.md)** - Start here if you're new to the library
- **[README](../README.md)** - Project overview and quick start

### 🔧 Advanced Topics
- **[Extensibility Guide](extensibility.md)** - Learn how to customize and extend the library
- **[API Reference](api-reference.md)** - Detailed documentation of all classes and methods

### 💡 Examples
- **[Example Implementations](examples/)** - Practical examples showing real-world usage
  - [SQLite Backend](examples/sqlite-backend.py) - Persistent storage implementation
  - [Webhook Notifications](examples/webhook-notifications.py) - Real-time notifications
  - [Enterprise Integration](examples/enterprise-integration.py) - Enterprise-grade features

## What is Kanban Core Library?

The Kanban Core Library is a comprehensive Python implementation of a kanban board system designed with flexibility and extensibility in mind. Whether you need a simple in-memory kanban board for a small application or a full-featured, enterprise-grade system with persistence, authentication, and real-time notifications, this library provides the building blocks you need.

### Key Features

- **📦 Zero Dependencies**: Core functionality requires only Python standard library
- **🔌 Extensible Architecture**: Plugin system for storage, search, and automation
- **🔒 Thread-Safe**: Built-in concurrency support
- **📊 Event-Driven**: Comprehensive event system for integrations
- **🛡️ Secure**: Granular permission system
- **📈 Analytics**: Built-in metrics and reporting
- **✅ Type-Safe**: Full type hints throughout

## Who Should Use This Library?

### Perfect For:
- **Application Developers** building project management features
- **SaaS Platforms** needing customizable workflow management
- **Enterprise Systems** requiring secure, auditable task tracking
- **Educational Projects** learning about software architecture patterns

### Use Cases:
- Project management tools
- Bug tracking systems
- Content publishing workflows
- Manufacturing process tracking
- Personal task management apps
- Team collaboration platforms

## Documentation Structure

### For New Users

1. **Start with [Basic Usage](basic-usage.md)**
   - Learn the SimpleKanban API
   - Understand core concepts
   - See common operations

2. **Review the [Examples](examples/)**
   - See working code
   - Understand patterns
   - Learn best practices

### For Advanced Users

1. **Read the [Extensibility Guide](extensibility.md)**
   - Implement custom storage backends
   - Add notification systems
   - Create automation rules
   - Build enterprise features

2. **Reference the [API Documentation](api-reference.md)**
   - Detailed method signatures
   - Exception handling
   - Type definitions

## Core Concepts

### 1. Boards
The top-level container that represents a project or workspace. Each board has:
- Multiple columns (workflow stages)
- Cards (tasks or items)
- Permissions (who can do what)
- Automation rules

### 2. Cards
Individual items that move through your workflow. Cards can have:
- Title and description
- Assignees
- Labels and tags
- Comments
- Custom fields
- Due dates

### 3. Columns
Represent stages in your workflow (e.g., "To Do", "In Progress", "Done"). Features:
- Ordered positioning
- WIP (Work In Progress) limits
- Custom names

### 4. Events
Everything that happens emits an event, enabling:
- Audit trails
- Real-time notifications
- Automation triggers
- Analytics

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   Your Application                   │
└─────────────────────────┬───────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────┐
│                   SimpleKanban                       │
│              (Ready-to-use implementation)           │
└─────────────────────────┬───────────────────────────┘
                          │ OR
┌─────────────────────────▼───────────────────────────┐
│                   KanbanFacade                       │
│            (Customizable implementation)             │
├─────────────┬─────────────┬─────────────┬──────────┤
│ Repository  │  Event Bus  │ Permissions │ Services │
│  (Storage)  │(Notifications)│ (Security) │ (Logic)  │
└─────────────┴─────────────┴─────────────┴──────────┘
```

## Common Patterns

### Basic Usage Pattern
```python
from kanban import SimpleKanban

# Initialize
kanban = SimpleKanban()

# Create board
board = kanban.create_board("user_id", "My Project")

# Add cards
card = kanban.add_card("user_id", board.id, "To Do", "Build feature")

# Move cards
kanban.move_card("user_id", board.id, card.id, "In Progress")
```

### Extension Pattern
```python
from kanban import KanbanFacade, EventBus

# Create custom components
repository = PostgreSQLRepository(connection_string)
notifier = SlackNotifier(webhook_url)

# Build custom kanban
event_bus = EventBus()
event_bus.subscribe("card.moved", notifier)

kanban = KanbanFacade(repository, event_bus)
```

## Best Practices

### 1. Error Handling
Always handle specific exceptions:
```python
from kanban.exceptions import BoardNotFoundError, PermissionDeniedError

try:
    board = kanban.get_board(user_id, board_id)
except BoardNotFoundError:
    # Handle missing board
except PermissionDeniedError:
    # Handle permission error
```

### 2. Event Subscriptions
Use events for cross-cutting concerns:
```python
# Don't do this - coupling business logic
def move_card_and_notify(card_id, column):
    kanban.move_card(user_id, board_id, card_id, column)
    send_notification(f"Card moved to {column}")

# Do this - use events
event_bus.subscribe("card.moved", notification_handler)
kanban.move_card(user_id, board_id, card_id, column)
```

### 3. Repository Design
Keep repositories focused on storage:
```python
# Good - repository handles storage only
class Repository(RepositoryInterface):
    def create_card(self, card: Card) -> Card:
        self.db.insert(card)
        return card

# Bad - mixing concerns
class Repository(RepositoryInterface):
    def create_card(self, card: Card) -> Card:
        self.db.insert(card)
        self.send_email(card.assignee)  # Don't do this!
        return card
```

## Performance Considerations

### 1. Caching
For production use, implement caching:
```python
class CachedRepository(RepositoryInterface):
    def __init__(self, base_repo, cache):
        self.repo = base_repo
        self.cache = cache
    
    def get_board(self, board_id: str) -> Optional[Board]:
        # Check cache first
        if cached := self.cache.get(f"board:{board_id}"):
            return cached
        
        # Fall back to repository
        board = self.repo.get_board(board_id)
        if board:
            self.cache.set(f"board:{board_id}", board)
        return board
```

### 2. Bulk Operations
Batch operations when possible:
```python
# Instead of multiple calls
for card_id in card_ids:
    kanban.move_card(user_id, board_id, card_id, "Done")

# Implement bulk operation
kanban.move_cards_bulk(user_id, board_id, card_ids, "Done")
```

### 3. Event Handling
Use async handlers for slow operations:
```python
class AsyncNotifier(EventHandler):
    async def handle(self, event: Event) -> None:
        # Non-blocking notification
        await self.send_notification_async(event)
```

## Testing Your Extensions

The library provides testing utilities:

```python
from kanban.testing import RepositoryTestMixin, create_test_board, create_test_card

class TestMyRepository(unittest.TestCase, RepositoryTestMixin):
    def setUp(self):
        self.repository = MyCustomRepository()
    
    def test_custom_feature(self):
        board = create_test_board()
        card = create_test_card(board.id)
        # Your test logic
```

## Migration Guide

### From Other Systems

If migrating from another kanban system:

1. **Map your data model** to the library's models
2. **Implement a custom repository** for your existing database
3. **Use events** to maintain compatibility with existing integrations
4. **Test thoroughly** with your production workflows

### Upgrading Versions

The library follows semantic versioning:
- **Patch releases** (1.0.x): Bug fixes only
- **Minor releases** (1.x.0): New features, backward compatible
- **Major releases** (x.0.0): May contain breaking changes

## Getting Help

### Resources
- **[GitHub Repository](https://github.com/redbaron/kanban-core)** - Source code and issue tracker
- **[API Reference](api-reference.md)** - Detailed API documentation
- **[Examples](examples/)** - Working code examples

### Common Issues

**Q: How do I implement authentication?**
A: Authentication is handled outside the library. Pass authenticated user IDs to the methods. See the [enterprise example](examples/enterprise-integration.py) for integration patterns.

**Q: Can I use this with my existing database?**
A: Yes! Implement the RepositoryInterface for your database. See the [SQLite example](examples/sqlite-backend.py) for guidance.

**Q: How do I scale this for thousands of users?**
A: Implement caching, use bulk operations, and consider sharding by organization. The architecture supports horizontal scaling.

## Contributing

We welcome contributions! Please:
1. Read the developer guide
2. Follow the code style
3. Add tests for new features
4. Update documentation
5. Submit a pull request

## License

This library is released under the MIT License. See the LICENSE file for details.