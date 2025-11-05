# Extensibility Guide

The Kanban Core Library is designed from the ground up to be extensible. While the `SimpleKanban` class provides a complete implementation using in-memory storage, you can easily plug in your own implementations for persistence, search, automation, and more.

## Architecture Overview

The library uses dependency injection and interfaces throughout, allowing you to replace any component:

```
┌─────────────────────────────────────────────────┐
│                  KanbanFacade                    │
│  (High-level API orchestrating all components)  │
└────────────────────────┬────────────────────────┘
                         │
    ┌────────────────────┼────────────────────┐
    │                    │                    │
┌───▼────────┐  ┌───────▼────────┐  ┌───────▼────────┐
│ Repository │  │   Event Bus    │  │  Permissions   │
│  (Storage) │  │ (Notifications)│  │   (Security)   │
└────────────┘  └────────────────┘  └────────────────┘
```

## Custom Repository Implementation

The most common extension point is implementing a custom repository for persistence.

### Repository Interface

```python
from kanban.repositories import RepositoryInterface
from kanban.models import Board, Card, User
from typing import List, Optional

class MyCustomRepository(RepositoryInterface):
    """Example repository using a hypothetical database."""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    # Board operations
    def create_board(self, board: Board) -> Board:
        # Save to your database
        self.db.boards.insert(board.to_dict())
        return board
    
    def get_board(self, board_id: str) -> Optional[Board]:
        data = self.db.boards.find_one({"id": board_id})
        return Board.from_dict(data) if data else None
    
    def update_board(self, board: Board) -> Board:
        self.db.boards.update({"id": board.id}, board.to_dict())
        return board
    
    def delete_board(self, board_id: str) -> None:
        self.db.boards.delete({"id": board_id})
    
    # Card operations
    def create_card(self, card: Card) -> Card:
        self.db.cards.insert(card.to_dict())
        return card
    
    def get_card(self, card_id: str) -> Optional[Card]:
        data = self.db.cards.find_one({"id": card_id})
        return Card.from_dict(data) if data else None
    
    def update_card(self, card: Card) -> Card:
        self.db.cards.update({"id": card.id}, card.to_dict())
        return card
    
    def delete_card(self, card_id: str) -> None:
        self.db.cards.delete({"id": card_id})
    
    def find_cards(self, board_id: str, **filters) -> List[Card]:
        query = {"board_id": board_id}
        query.update(filters)
        results = self.db.cards.find(query)
        return [Card.from_dict(data) for data in results]
```

### Using Your Custom Repository

```python
from kanban import KanbanFacade, EventBus

# Initialize your repository
db_connection = MyDatabase.connect("postgresql://...")
repository = MyCustomRepository(db_connection)

# Create the kanban facade with your repository
event_bus = EventBus()
kanban = KanbanFacade(repository, event_bus)

# Use it exactly like SimpleKanban
board = kanban.create_board("user123", "My Project")
```

## Custom Search Implementation

For advanced search capabilities, you can implement a custom search service:

```python
from kanban.services import SearchService
from kanban.models import Card
from typing import List
import elasticsearch

class ElasticsearchService(SearchService):
    def __init__(self, es_client):
        self.es = es_client
        self.index = "kanban_cards"
    
    def index_card(self, card: Card) -> None:
        """Index a card for searching."""
        self.es.index(
            index=self.index,
            id=card.id,
            body={
                "board_id": card.board_id,
                "title": card.title,
                "description": card.description,
                "labels": card.labels,
                "assignee": card.assignee,
                "column": card.column,
                "created_at": card.created_at.isoformat()
            }
        )
    
    def search_cards(
        self, 
        board_id: str, 
        text: Optional[str] = None,
        labels: Optional[List[str]] = None,
        assignee: Optional[str] = None
    ) -> List[str]:
        """Search cards and return matching IDs."""
        must_clauses = [{"term": {"board_id": board_id}}]
        
        if text:
            must_clauses.append({
                "multi_match": {
                    "query": text,
                    "fields": ["title^2", "description"]
                }
            })
        
        if labels:
            for label in labels:
                must_clauses.append({"term": {"labels": label}})
        
        if assignee is not None:
            must_clauses.append({"term": {"assignee": assignee}})
        
        response = self.es.search(
            index=self.index,
            body={"query": {"bool": {"must": must_clauses}}}
        )
        
        return [hit["_id"] for hit in response["hits"]["hits"]]
    
    def delete_card(self, card_id: str) -> None:
        """Remove a card from the search index."""
        self.es.delete(index=self.index, id=card_id)
```

### Integrating Custom Search

```python
from kanban import KanbanFacade

# Setup Elasticsearch
es_client = elasticsearch.Elasticsearch(['localhost:9200'])
search_service = ElasticsearchService(es_client)

# Create facade with custom search
kanban = KanbanFacade(
    repository=repository,
    event_bus=event_bus,
    search_service=search_service
)

# Cards are now automatically indexed in Elasticsearch
card = kanban.add_card("user123", board.id, "To Do", "Implement search")

# Advanced search capabilities
results = kanban.search_cards("user123", board.id, text="implement AND search")
```

## Custom Event Handlers

The event system allows you to react to all operations in the kanban board:

### Available Events

- `board.created`, `board.updated`, `board.deleted`
- `card.created`, `card.updated`, `card.deleted`, `card.moved`
- `column.added`, `column.removed`, `column.renamed`
- `comment.added`, `comment.updated`, `comment.deleted`
- `label.added`, `label.removed`
- `user.assigned`, `user.unassigned`

### Creating Event Handlers

```python
from kanban.events import Event, EventHandler
import requests

class SlackNotifier(EventHandler):
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url
    
    def handle(self, event: Event) -> None:
        if event.type == "card.moved":
            card = event.data["card"]
            from_column = event.data["from_column"]
            to_column = event.data["to_column"]
            
            message = {
                "text": f"Card '{card.title}' moved from {from_column} to {to_column}"
            }
            requests.post(self.webhook_url, json=message)

class AuditLogger(EventHandler):
    def __init__(self, audit_repository):
        self.audit_repo = audit_repository
    
    def handle(self, event: Event) -> None:
        # Log all events to an audit trail
        self.audit_repo.log({
            "timestamp": event.timestamp,
            "type": event.type,
            "user_id": event.user_id,
            "board_id": event.board_id,
            "data": event.data
        })

# Register handlers
event_bus = EventBus()
event_bus.subscribe("card.moved", SlackNotifier("https://hooks.slack.com/..."))
event_bus.subscribe("*", AuditLogger(audit_repo))  # Subscribe to all events
```

## Custom Permissions

Implement fine-grained access control:

```python
from kanban.permissions import PermissionChecker
from kanban.models import Permission

class RoleBasedPermissions(PermissionChecker):
    def __init__(self, role_service):
        self.role_service = role_service
    
    def check_permission(
        self, 
        user_id: str, 
        resource_type: str,
        resource_id: str,
        action: str
    ) -> bool:
        # Get user's role for the board
        if resource_type == "board":
            board_id = resource_id
        else:  # card, column, etc.
            # Get board_id from the resource
            board_id = self.get_board_id_for_resource(resource_type, resource_id)
        
        user_role = self.role_service.get_user_role(user_id, board_id)
        
        # Define permission matrix
        permissions = {
            "owner": ["create", "read", "update", "delete", "manage"],
            "admin": ["create", "read", "update", "delete"],
            "member": ["create", "read", "update"],
            "viewer": ["read"]
        }
        
        allowed_actions = permissions.get(user_role, [])
        return action in allowed_actions

# Use custom permissions
permission_checker = RoleBasedPermissions(role_service)
kanban = KanbanFacade(
    repository=repository,
    event_bus=event_bus,
    permission_checker=permission_checker
)
```

## Custom Automation Rules

Create sophisticated automation rules:

```python
from kanban.automation import AutomationRule
from kanban.models import Card
import re

class RegexLabelRule(AutomationRule):
    """Automatically add labels based on card content."""
    
    def __init__(self, patterns):
        self.patterns = patterns  # Dict of {label: regex_pattern}
    
    def should_apply(self, card: Card, trigger: str) -> bool:
        return trigger in ["card.created", "card.updated"]
    
    def apply(self, card: Card) -> Card:
        text = f"{card.title} {card.description or ''}"
        
        for label, pattern in self.patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                if label not in card.labels:
                    card.labels.append(label)
        
        return card

class DueDateRule(AutomationRule):
    """Move cards to 'Urgent' column when due date is near."""
    
    def __init__(self, days_before=2):
        self.days_before = days_before
    
    def should_apply(self, card: Card, trigger: str) -> bool:
        if not card.due_date:
            return False
        
        days_until_due = (card.due_date - datetime.now()).days
        return days_until_due <= self.days_before
    
    def apply(self, card: Card) -> Card:
        card.column = "Urgent"
        if "urgent" not in card.labels:
            card.labels.append("urgent")
        return card

# Add rules to a board
regex_rule = RegexLabelRule({
    "bug": r"\b(bug|error|issue|problem)\b",
    "feature": r"\b(feature|enhancement|improve)\b",
    "documentation": r"\b(docs?|documentation|readme)\b"
})

board.automation_rules.extend([regex_rule, DueDateRule()])
```

## Custom Metrics Calculator

Implement specialized metrics:

```python
from kanban.metrics import MetricsCalculator
from kanban.models import Board, Card
from datetime import datetime, timedelta
from typing import Dict, Any

class AgileMetricsCalculator(MetricsCalculator):
    def calculate_velocity(self, board: Board, sprint_days: int = 14) -> float:
        """Calculate team velocity (story points per sprint)."""
        sprint_start = datetime.now() - timedelta(days=sprint_days)
        
        completed_points = 0
        for card in self.get_cards_completed_since(board, sprint_start):
            # Assume story points are stored in custom fields
            points = card.custom_fields.get("story_points", 0)
            completed_points += points
        
        return completed_points
    
    def calculate_burndown(self, board: Board, sprint_start: datetime) -> Dict[str, Any]:
        """Generate burndown chart data."""
        total_points = sum(
            card.custom_fields.get("story_points", 0)
            for card in board.get_all_cards()
        )
        
        daily_progress = []
        current_date = sprint_start
        
        while current_date <= datetime.now():
            remaining_points = sum(
                card.custom_fields.get("story_points", 0)
                for card in board.get_all_cards()
                if card.column != "Done" or card.completed_at > current_date
            )
            
            daily_progress.append({
                "date": current_date.isoformat(),
                "remaining_points": remaining_points
            })
            
            current_date += timedelta(days=1)
        
        return {
            "total_points": total_points,
            "daily_progress": daily_progress
        }

# Use custom metrics
metrics_calc = AgileMetricsCalculator(repository)
velocity = metrics_calc.calculate_velocity(board)
burndown = metrics_calc.calculate_burndown(board, sprint_start)
```

## Complete Custom Implementation Example

Here's a complete example using PostgreSQL, Redis, and custom components:

```python
import psycopg2
import redis
from kanban import KanbanFacade, EventBus
from typing import Optional, List

class PostgresRepository(RepositoryInterface):
    def __init__(self, connection_string):
        self.conn = psycopg2.connect(connection_string)
        self.init_schema()
    
    def init_schema(self):
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS boards (
                    id VARCHAR(36) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    owner_id VARCHAR(36) NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    data JSONB NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS cards (
                    id VARCHAR(36) PRIMARY KEY,
                    board_id VARCHAR(36) NOT NULL REFERENCES boards(id),
                    column_name VARCHAR(100) NOT NULL,
                    position INTEGER NOT NULL,
                    data JSONB NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
            """)
            self.conn.commit()
    
    def create_board(self, board: Board) -> Board:
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO boards (id, name, owner_id, created_at, data) 
                   VALUES (%s, %s, %s, %s, %s)""",
                (board.id, board.name, board.owner_id, board.created_at, board.to_json())
            )
            self.conn.commit()
        return board
    
    # ... implement other methods ...

class RedisCacheLayer:
    def __init__(self, redis_client, repository):
        self.redis = redis_client
        self.repository = repository
        self.ttl = 3600  # 1 hour cache
    
    def get_board(self, board_id: str) -> Optional[Board]:
        # Try cache first
        cached = self.redis.get(f"board:{board_id}")
        if cached:
            return Board.from_json(cached)
        
        # Fall back to database
        board = self.repository.get_board(board_id)
        if board:
            self.redis.setex(f"board:{board_id}", self.ttl, board.to_json())
        return board
    
    def invalidate_board(self, board_id: str):
        self.redis.delete(f"board:{board_id}")
        # Also invalidate related cards
        self.redis.delete(f"cards:{board_id}:*")

class ProductionKanban:
    def __init__(self, db_url, redis_url, webhook_url):
        # Setup repositories
        postgres_repo = PostgresRepository(db_url)
        redis_client = redis.from_url(redis_url)
        cached_repo = RedisCacheLayer(redis_client, postgres_repo)
        
        # Setup event bus with handlers
        event_bus = EventBus()
        event_bus.subscribe("*", AuditLogger(postgres_repo))
        event_bus.subscribe("card.moved", SlackNotifier(webhook_url))
        
        # Cache invalidation on updates
        def invalidate_cache(event):
            if "board_id" in event.data:
                cached_repo.invalidate_board(event.data["board_id"])
        
        event_bus.subscribe("*.updated", invalidate_cache)
        event_bus.subscribe("*.deleted", invalidate_cache)
        
        # Create the facade
        self.kanban = KanbanFacade(
            repository=cached_repo,
            event_bus=event_bus,
            permission_checker=RoleBasedPermissions(role_service),
            metrics_calculator=AgileMetricsCalculator(cached_repo)
        )
    
    def get_kanban(self):
        return self.kanban

# Usage
production_kanban = ProductionKanban(
    db_url="postgresql://user:pass@localhost/kanban",
    redis_url="redis://localhost:6379",
    webhook_url="https://hooks.slack.com/..."
)

kanban = production_kanban.get_kanban()
# Use exactly like SimpleKanban, but with production-ready features
```

## Serialization Considerations for Custom Repositories

### Important Limitation: Callable Storage

When implementing custom repositories for persistent storage, be aware that `AutomationRule` and `ColumnPolicy` objects contain Python callable functions that cannot be serialized using standard methods (JSON, pickle over network, etc.).

#### Affected Objects

1. **AutomationRule**: Contains `trigger` and `action` callables
2. **ColumnPolicy**: Contains `entry_criteria` and `exit_criteria` callables

#### Impact on Custom Repositories

If you're implementing a database-backed repository, you have several options:

##### Option 1: Exclude Automation Rules from Serialization

```python
class DatabaseRepository(IKanbanRepository):
    def save(self, board: Board, expected_version: int | None = None) -> Board:
        # Create a copy without automation rules
        board_data = {
            "id": board.id,
            "name": board.name,
            "columns": self._serialize_columns(board.columns),
            "cards": self._serialize_cards(board.cards),
            # Note: automation_rules intentionally omitted
        }

        # Save to database
        self.db.save_board(board_data)

        # Return the original board (with rules intact in memory)
        return board

    def get(self, board_id: str) -> Board | None:
        data = self.db.get_board(board_id)
        if not data:
            return None

        board = Board(**data)
        # Automation rules must be added programmatically after loading
        board.automation_rules = self._get_default_rules()
        return board
```

##### Option 2: Rule Registry Pattern

Maintain a registry of named rules that can be referenced by ID:

```python
from kanban import create_auto_move_rule, create_due_date_warning_rule

# Global registry of automation rules
AUTOMATION_RULE_REGISTRY = {
    "auto-move-ready": create_auto_move_rule("ready", "In Progress"),
    "auto-move-done": create_auto_move_rule("done", "Done"),
    "due-date-warning-3d": create_due_date_warning_rule(3),
    "due-date-warning-7d": create_due_date_warning_rule(7),
}

class DatabaseRepository(IKanbanRepository):
    def save(self, board: Board, expected_version: int | None = None) -> Board:
        # Extract rule IDs instead of the rules themselves
        rule_ids = [rule.id for rule in board.automation_rules]

        board_data = {
            "id": board.id,
            "name": board.name,
            "rule_ids": rule_ids,  # Store IDs only
            # ... other fields
        }

        self.db.save_board(board_data)
        return board

    def get(self, board_id: str) -> Board | None:
        data = self.db.get_board(board_id)
        if not data:
            return None

        # Reconstruct board
        board = Board(id=data["id"], name=data["name"])

        # Restore automation rules from registry
        for rule_id in data.get("rule_ids", []):
            if rule_id in AUTOMATION_RULE_REGISTRY:
                board.automation_rules.append(AUTOMATION_RULE_REGISTRY[rule_id])

        return board
```

##### Option 3: Separate Configuration Storage

Store rule configurations separately from board data:

```python
class DatabaseRepository(IKanbanRepository):
    def __init__(self, db_connection, rule_config_path: str):
        self.db = db_connection
        self.rule_config = self._load_rule_config(rule_config_path)

    def _load_rule_config(self, path: str) -> dict:
        # Load rule definitions from config file (YAML, JSON, etc.)
        import yaml
        with open(path) as f:
            return yaml.safe_load(f)

    def _build_rules_from_config(self, rule_names: list[str]) -> list[AutomationRule]:
        rules = []
        for name in rule_names:
            config = self.rule_config.get(name)
            if config:
                # Build rule based on configuration
                rule = self._create_rule_from_config(config)
                rules.append(rule)
        return rules
```

### Column Policies

Similar considerations apply to `ColumnPolicy` objects with custom `entry_criteria` and `exit_criteria`:

```python
# Instead of storing callables
policy = ColumnPolicy(
    wip_limit=5,
    entry_criteria=lambda card: "ready" in card.custom_fields.get("labels", set())
)

# Use configuration-based approach
policy_config = {
    "wip_limit": 5,
    "entry_criteria": {
        "type": "label_check",
        "label": "ready"
    }
}

# Then rebuild the callable from config when loading
def build_entry_criteria(config):
    if config["type"] == "label_check":
        label = config["label"]
        return lambda card: label in card.custom_fields.get("labels", set())
```

### Future Direction

We are planning to introduce a serializable rule definition language in a future version that will eliminate these limitations and enable full board serialization including automation logic.

## Best Practices

1. **Use Interfaces**: Always program against the interfaces, not concrete implementations
2. **Event-Driven**: Use events for cross-cutting concerns rather than coupling components
3. **Fail Gracefully**: Handle errors in custom components without breaking core functionality
4. **Test Thoroughly**: Write tests for your custom implementations
5. **Document**: Clearly document any custom behavior or requirements
6. **Handle Non-Serializable Objects**: Be aware of callable storage limitations when implementing persistent repositories

## Testing Custom Implementations

```python
import unittest
from kanban.testing import RepositoryTestMixin

class TestPostgresRepository(unittest.TestCase, RepositoryTestMixin):
    def setUp(self):
        # Setup test database
        self.repository = PostgresRepository("postgresql://test:test@localhost/test_kanban")
    
    def tearDown(self):
        # Clean up test data
        self.repository.cleanup()
    
    # The mixin provides all standard repository tests
    # Add any custom tests here

class TestCustomAutomation(unittest.TestCase):
    def test_regex_label_rule(self):
        rule = RegexLabelRule({"bug": r"\bbug\b"})
        card = Card(id="1", title="Fix bug in login", labels=[])
        
        updated_card = rule.apply(card)
        self.assertIn("bug", updated_card.labels)
```

This extensibility guide demonstrates how the Kanban Core Library can be adapted to virtually any use case while maintaining a clean, consistent API.