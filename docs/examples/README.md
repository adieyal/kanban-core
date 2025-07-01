# Kanban Core Library Examples

This directory contains practical examples demonstrating various ways to extend and use the Kanban Core Library.

## Examples Overview

### 1. [SQLite Backend](sqlite-backend.py)
Demonstrates implementing a persistent storage backend using SQLite.

**Key features:**
- Complete repository implementation with SQLite
- Database schema initialization
- Transaction support
- Query optimization with indexes
- Data serialization/deserialization

**Use this when:**
- You need local file-based persistence
- Building desktop or small-scale applications
- Prototyping before moving to a larger database

### 2. [Webhook Notifications](webhook-notifications.py)
Shows how to send real-time notifications to external services.

**Key features:**
- Support for Slack, Discord, Teams, and generic webhooks
- Event filtering and routing
- Rate limiting to prevent spam
- Retry logic for failed webhooks
- Custom message formatting per platform

**Use this when:**
- Integrating with team communication tools
- Building real-time dashboards
- Creating notification systems
- Triggering external workflows

### 3. [Enterprise Integration](enterprise-integration.py)
Comprehensive example of enterprise-grade features.

**Key features:**
- LDAP/Active Directory authentication
- Role-based access control (RBAC)
- Multi-tenancy support
- Audit logging with encryption
- Session management
- Compliance features

**Use this when:**
- Building for enterprise environments
- Need advanced security features
- Require compliance and audit trails
- Supporting multiple organizations

## Running the Examples

Each example is a standalone Python script that can be run directly:

```bash
# Make sure kanban-core is installed
pip install kanban-core

# Run an example
python sqlite-backend.py
python webhook-notifications.py
python enterprise-integration.py
```

## Common Patterns

### 1. Dependency Injection
All examples use dependency injection to extend functionality:

```python
from kanban import KanbanFacade, EventBus

# Create your custom components
repository = CustomRepository()
event_bus = EventBus()
permission_checker = CustomPermissions()

# Inject them into the facade
kanban = KanbanFacade(
    repository=repository,
    event_bus=event_bus,
    permission_checker=permission_checker
)
```

### 2. Event Handling
Subscribe to events for cross-cutting concerns:

```python
def handle_card_moved(event):
    print(f"Card {event.data['card_id']} moved to {event.data['to_column']}")

event_bus.subscribe("card.moved", handle_card_moved)
```

### 3. Custom Repositories
Implement the RepositoryInterface for custom storage:

```python
class MyRepository(RepositoryInterface):
    def create_board(self, board: Board) -> Board:
        # Your implementation
        pass
    
    # ... implement other required methods
```

## Creating Your Own Extensions

When creating your own extensions, follow these principles:

1. **Use Interfaces**: Always implement the provided interfaces rather than extending concrete classes
2. **Handle Errors Gracefully**: Don't let your extensions break core functionality
3. **Document Behavior**: Clearly document any special behavior or requirements
4. **Test Thoroughly**: Write comprehensive tests for your extensions
5. **Consider Performance**: Cache where appropriate, batch operations when possible

## Testing Extensions

The library provides test mixins to help test custom implementations:

```python
from kanban.testing import RepositoryTestMixin
import unittest

class TestMyRepository(unittest.TestCase, RepositoryTestMixin):
    def setUp(self):
        self.repository = MyRepository()
    
    # The mixin provides standard test cases
    # Add your custom tests here
```

## Additional Examples

For more examples and use cases, see:
- The [test suite](../../tests/) for comprehensive usage examples
- The [API documentation](../api-reference.md) for detailed method signatures
- The [extensibility guide](../extensibility.md) for architecture details

## Contributing Examples

If you've created an interesting extension or use case, we'd love to include it! Please:
1. Follow the existing example format
2. Include comprehensive comments
3. Add error handling and edge cases
4. Provide clear documentation
5. Submit a pull request

## Questions?

If you have questions about these examples or need help with your own extensions, please:
- Check the [documentation](../)
- Open an issue on GitHub
- Join our community discussions