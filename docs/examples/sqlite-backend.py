#!/usr/bin/env python3
"""
SQLite Backend Example

This example shows how to implement a SQLite-based repository for persistent
storage of kanban boards and cards.
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

from kanban import KanbanFacade, EventBus
from kanban.repositories import RepositoryInterface
from kanban.models import Board, Card, Column, User, Comment
from kanban.exceptions import BoardNotFoundError, CardNotFoundError


class SQLiteRepository(RepositoryInterface):
    """Repository implementation using SQLite for persistence."""
    
    def __init__(self, db_path: str = "kanban.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS boards (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    data TEXT NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cards (
                    id TEXT PRIMARY KEY,
                    board_id TEXT NOT NULL,
                    column_name TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    data TEXT NOT NULL,
                    FOREIGN KEY (board_id) REFERENCES boards (id) ON DELETE CASCADE
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cards_board 
                ON cards (board_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cards_column 
                ON cards (board_id, column_name)
            """)
    
    def _serialize_board(self, board: Board) -> Dict[str, Any]:
        """Convert board to dictionary for storage."""
        return {
            "id": board.id,
            "name": board.name,
            "owner_id": board.owner_id,
            "created_at": board.created_at.isoformat(),
            "updated_at": board.updated_at.isoformat(),
            "columns": [
                {
                    "name": col.name,
                    "position": col.position,
                    "wip_limit": col.wip_limit
                }
                for col in board.columns
            ],
            "permissions": [
                {
                    "user_id": perm.user_id,
                    "role": perm.role
                }
                for perm in board.permissions
            ],
            "automation_rules": []  # Simplified for this example
        }
    
    def _deserialize_board(self, data: Dict[str, Any]) -> Board:
        """Convert dictionary to board object."""
        board = Board(
            id=data["id"],
            name=data["name"],
            owner_id=data["owner_id"]
        )
        board.created_at = datetime.fromisoformat(data["created_at"])
        board.updated_at = datetime.fromisoformat(data["updated_at"])
        
        # Recreate columns
        board.columns = []
        for col_data in data.get("columns", []):
            column = Column(
                name=col_data["name"],
                position=col_data["position"],
                wip_limit=col_data.get("wip_limit")
            )
            board.columns.append(column)
        
        return board
    
    def _serialize_card(self, card: Card) -> Dict[str, Any]:
        """Convert card to dictionary for storage."""
        return {
            "id": card.id,
            "board_id": card.board_id,
            "column": card.column,
            "position": card.position,
            "title": card.title,
            "description": card.description,
            "assignee": card.assignee,
            "labels": card.labels,
            "due_date": card.due_date.isoformat() if card.due_date else None,
            "created_at": card.created_at.isoformat(),
            "updated_at": card.updated_at.isoformat(),
            "custom_fields": card.custom_fields,
            "comments": [
                {
                    "id": comment.id,
                    "author": comment.author,
                    "text": comment.text,
                    "created_at": comment.created_at.isoformat()
                }
                for comment in card.comments
            ]
        }
    
    def _deserialize_card(self, data: Dict[str, Any]) -> Card:
        """Convert dictionary to card object."""
        card = Card(
            id=data["id"],
            board_id=data["board_id"],
            column=data["column"],
            position=data["position"],
            title=data["title"]
        )
        
        card.description = data.get("description")
        card.assignee = data.get("assignee")
        card.labels = data.get("labels", [])
        card.custom_fields = data.get("custom_fields", {})
        
        if data.get("due_date"):
            card.due_date = datetime.fromisoformat(data["due_date"])
        
        card.created_at = datetime.fromisoformat(data["created_at"])
        card.updated_at = datetime.fromisoformat(data["updated_at"])
        
        # Recreate comments
        for comment_data in data.get("comments", []):
            comment = Comment(
                id=comment_data["id"],
                author=comment_data["author"],
                text=comment_data["text"]
            )
            comment.created_at = datetime.fromisoformat(comment_data["created_at"])
            card.comments.append(comment)
        
        return card
    
    # Board operations
    def create_board(self, board: Board) -> Board:
        board_data = self._serialize_board(board)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO boards (id, name, owner_id, created_at, updated_at, data)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                board.id,
                board.name,
                board.owner_id,
                board_data["created_at"],
                board_data["updated_at"],
                json.dumps(board_data)
            ))
        
        return board
    
    def get_board(self, board_id: str) -> Optional[Board]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT data FROM boards WHERE id = ?",
                (board_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return self._deserialize_board(json.loads(row[0]))
    
    def update_board(self, board: Board) -> Board:
        board.updated_at = datetime.utcnow()
        board_data = self._serialize_board(board)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE boards 
                SET name = ?, updated_at = ?, data = ?
                WHERE id = ?
            """, (
                board.name,
                board_data["updated_at"],
                json.dumps(board_data),
                board.id
            ))
        
        return board
    
    def delete_board(self, board_id: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM boards WHERE id = ?", (board_id,))
    
    def list_boards(self, user_id: str) -> List[Board]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT data FROM boards 
                WHERE owner_id = ? OR 
                      data LIKE ?
                ORDER BY created_at DESC
            """, (user_id, f'%"user_id": "{user_id}"%'))
            
            boards = []
            for row in cursor:
                board = self._deserialize_board(json.loads(row[0]))
                boards.append(board)
            
            return boards
    
    # Card operations
    def create_card(self, card: Card) -> Card:
        card_data = self._serialize_card(card)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO cards 
                (id, board_id, column_name, position, title, created_at, updated_at, data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                card.id,
                card.board_id,
                card.column,
                card.position,
                card.title,
                card_data["created_at"],
                card_data["updated_at"],
                json.dumps(card_data)
            ))
        
        return card
    
    def get_card(self, card_id: str) -> Optional[Card]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT data FROM cards WHERE id = ?",
                (card_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return self._deserialize_card(json.loads(row[0]))
    
    def update_card(self, card: Card) -> Card:
        card.updated_at = datetime.utcnow()
        card_data = self._serialize_card(card)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE cards 
                SET board_id = ?, column_name = ?, position = ?, 
                    title = ?, updated_at = ?, data = ?
                WHERE id = ?
            """, (
                card.board_id,
                card.column,
                card.position,
                card.title,
                card_data["updated_at"],
                json.dumps(card_data),
                card.id
            ))
        
        return card
    
    def delete_card(self, card_id: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))
    
    def find_cards(self, board_id: str, **filters) -> List[Card]:
        query = "SELECT data FROM cards WHERE board_id = ?"
        params = [board_id]
        
        if "column" in filters:
            query += " AND column_name = ?"
            params.append(filters["column"])
        
        if "assignee" in filters:
            if filters["assignee"]:
                query += " AND data LIKE ?"
                params.append(f'%"assignee": "{filters["assignee"]}"%')
            else:
                query += " AND (data NOT LIKE ? OR data LIKE ?)"
                params.extend(['%"assignee": "%', '%"assignee": null%'])
        
        query += " ORDER BY position"
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            
            cards = []
            for row in cursor:
                card_data = json.loads(row[0])
                
                # Apply label filter in Python (simpler than complex SQL)
                if "labels" in filters:
                    required_labels = filters["labels"]
                    card_labels = card_data.get("labels", [])
                    if not all(label in card_labels for label in required_labels):
                        continue
                
                # Apply text search in Python
                if "text" in filters:
                    search_text = filters["text"].lower()
                    title = card_data.get("title", "").lower()
                    description = card_data.get("description", "").lower()
                    if search_text not in title and search_text not in description:
                        continue
                
                cards.append(self._deserialize_card(card_data))
            
            return cards
    
    def get_cards_by_column(self, board_id: str, column: str) -> List[Card]:
        return self.find_cards(board_id, column=column)
    
    # User operations (simplified)
    def create_user(self, user: User) -> User:
        # In a real implementation, you'd have a users table
        return user
    
    def get_user(self, user_id: str) -> Optional[User]:
        # For this example, we'll create a dummy user
        return User(id=user_id, email=f"{user_id}@example.com")
    
    def get_board_cards(self, board_id: str) -> List[Card]:
        """Get all cards for a board."""
        return self.find_cards(board_id)


def demo_sqlite_backend():
    """Demonstrate using SQLite backend."""
    print("=== SQLite Backend Demo ===\n")
    
    # Create a SQLite-backed kanban instance
    db_path = Path("demo_kanban.db")
    repository = SQLiteRepository(str(db_path))
    event_bus = EventBus()
    
    # Subscribe to events for logging
    def log_event(event):
        print(f"Event: {event.type} - {event.data.get('title', event.data.get('name', ''))}")
    
    event_bus.subscribe("*", log_event)
    
    # Create the kanban facade
    kanban = KanbanFacade(repository, event_bus)
    
    # Create a board
    print("Creating board...")
    board = kanban.create_board("demo_user", "SQLite Demo Project")
    print(f"Created board: {board.name} (ID: {board.id})\n")
    
    # Add some cards
    print("Adding cards...")
    cards = []
    tasks = [
        ("Setup database schema", "Create tables for persistent storage"),
        ("Implement CRUD operations", "Add create, read, update, delete methods"),
        ("Add indexing", "Create indexes for better query performance"),
        ("Write tests", "Ensure all operations work correctly")
    ]
    
    for title, description in tasks:
        card = kanban.add_card(
            "demo_user",
            board.id,
            "To Do",
            title,
            description=description
        )
        cards.append(card)
        print(f"Added: {card.title}")
    
    # Move some cards
    print("\nMoving cards...")
    kanban.move_card("demo_user", board.id, cards[0].id, "In Progress")
    kanban.move_card("demo_user", board.id, cards[1].id, "In Progress")
    
    # Update a card
    print("\nUpdating card...")
    kanban.update_card(
        "demo_user",
        board.id,
        cards[0].id,
        assignee="developer1",
        labels=["database", "infrastructure"]
    )
    
    # Add a comment
    print("\nAdding comment...")
    kanban.add_comment(
        "demo_user",
        board.id,
        cards[0].id,
        "Schema design is complete, ready for review"
    )
    
    # Search cards
    print("\nSearching for 'database' cards...")
    results = kanban.search_cards("demo_user", board.id, text="database")
    for card in results:
        print(f"Found: {card.title}")
    
    # Get board state
    print("\nCurrent board state:")
    board_data = kanban.get_board("demo_user", board.id)
    for column in board_data.columns:
        print(f"\n{column.name}:")
        column_cards = repository.get_cards_by_column(board.id, column.name)
        for card in column_cards:
            print(f"  - {card.title}")
            if card.assignee:
                print(f"    Assigned to: {card.assignee}")
            if card.labels:
                print(f"    Labels: {', '.join(card.labels)}")
    
    # Demonstrate persistence
    print("\n\nDemonstrating persistence...")
    print("Creating new kanban instance with same database...")
    
    # Create a new instance
    repository2 = SQLiteRepository(str(db_path))
    event_bus2 = EventBus()
    kanban2 = KanbanFacade(repository2, event_bus2)
    
    # Load the board
    loaded_board = kanban2.get_board("demo_user", board.id)
    print(f"Loaded board: {loaded_board.name}")
    
    # Show that cards are persisted
    loaded_cards = repository2.get_board_cards(board.id)
    print(f"Found {len(loaded_cards)} persisted cards")
    
    # Cleanup
    print(f"\nDemo complete. Database saved to: {db_path.absolute()}")
    print("To clean up, delete the demo_kanban.db file")


if __name__ == "__main__":
    demo_sqlite_backend()