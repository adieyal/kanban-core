#!/usr/bin/env python3
"""
Webhook Notifications Example

This example demonstrates how to implement webhook notifications for various
kanban events, supporting multiple notification channels like Slack, Discord,
and custom webhooks.
"""

import json
import urllib.request
import urllib.error
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from kanban import SimpleKanban, EventBus
from kanban.events import Event, EventHandler


class WebhookType(Enum):
    """Supported webhook types."""
    SLACK = "slack"
    DISCORD = "discord"
    TEAMS = "teams"
    GENERIC = "generic"


@dataclass
class WebhookConfig:
    """Configuration for a webhook endpoint."""
    url: str
    type: WebhookType
    events: List[str]  # List of event types to send
    headers: Optional[Dict[str, str]] = None
    retry_count: int = 3
    timeout: int = 10


class WebhookNotifier(EventHandler):
    """Send notifications to webhook endpoints for kanban events."""
    
    def __init__(self, configs: List[WebhookConfig]):
        self.configs = configs
        self.formatters = {
            WebhookType.SLACK: self._format_slack_message,
            WebhookType.DISCORD: self._format_discord_message,
            WebhookType.TEAMS: self._format_teams_message,
            WebhookType.GENERIC: self._format_generic_message
        }
    
    def handle(self, event: Event) -> None:
        """Handle an event by sending to configured webhooks."""
        for config in self.configs:
            # Check if this webhook wants this event type
            if not self._should_notify(event.type, config.events):
                continue
            
            try:
                # Format message based on webhook type
                formatter = self.formatters[config.type]
                message = formatter(event)
                
                # Send the webhook
                self._send_webhook(config, message)
                
            except Exception as e:
                print(f"Failed to send webhook to {config.url}: {e}")
    
    def _should_notify(self, event_type: str, configured_events: List[str]) -> bool:
        """Check if an event type matches configured patterns."""
        if "*" in configured_events:
            return True
        
        for pattern in configured_events:
            if pattern.endswith("*"):
                prefix = pattern[:-1]
                if event_type.startswith(prefix):
                    return True
            elif event_type == pattern:
                return True
        
        return False
    
    def _send_webhook(self, config: WebhookConfig, message: Dict[str, Any]) -> None:
        """Send a webhook with retry logic."""
        headers = config.headers or {}
        headers["Content-Type"] = "application/json"
        
        data = json.dumps(message).encode("utf-8")
        
        for attempt in range(config.retry_count):
            try:
                req = urllib.request.Request(
                    config.url,
                    data=data,
                    headers=headers,
                    method="POST"
                )
                
                with urllib.request.urlopen(req, timeout=config.timeout) as response:
                    if response.status < 300:
                        return  # Success
                    
            except urllib.error.URLError as e:
                if attempt < config.retry_count - 1:
                    print(f"Webhook attempt {attempt + 1} failed, retrying...")
                    continue
                raise
    
    def _format_slack_message(self, event: Event) -> Dict[str, Any]:
        """Format message for Slack webhook."""
        emoji_map = {
            "card.created": "📝",
            "card.moved": "➡️",
            "card.updated": "✏️",
            "card.deleted": "🗑️",
            "board.created": "📋",
            "comment.added": "💬"
        }
        
        emoji = emoji_map.get(event.type, "📌")
        
        # Build message based on event type
        if event.type == "card.created":
            card = event.data["card"]
            text = f"{emoji} New card created: *{card.title}*"
            fields = [
                {"title": "Board", "value": event.data.get("board_name", "Unknown"), "short": True},
                {"title": "Column", "value": card.column, "short": True}
            ]
            if card.assignee:
                fields.append({"title": "Assignee", "value": card.assignee, "short": True})
            
        elif event.type == "card.moved":
            card = event.data["card"]
            from_col = event.data["from_column"]
            to_col = event.data["to_column"]
            text = f"{emoji} Card moved: *{card.title}*"
            fields = [
                {"title": "From", "value": from_col, "short": True},
                {"title": "To", "value": to_col, "short": True}
            ]
            
        elif event.type == "card.updated":
            card = event.data["card"]
            changes = event.data.get("changes", {})
            text = f"{emoji} Card updated: *{card.title}*"
            fields = []
            
            for field, value in changes.items():
                if field == "assignee":
                    fields.append({"title": "Assignee", "value": value or "Unassigned", "short": True})
                elif field == "labels":
                    fields.append({"title": "Labels", "value": ", ".join(value), "short": True})
                elif field == "description":
                    fields.append({"title": "Description", "value": "Updated", "short": True})
        
        elif event.type == "comment.added":
            comment = event.data["comment"]
            card_title = event.data.get("card_title", "Unknown card")
            text = f"{emoji} New comment on *{card_title}*"
            fields = [
                {"title": "Author", "value": comment.author, "short": True},
                {"title": "Comment", "value": comment.text, "short": False}
            ]
        
        else:
            text = f"{emoji} Event: {event.type}"
            fields = []
        
        # Build Slack attachment
        attachment = {
            "text": text,
            "fields": fields,
            "footer": "Kanban Bot",
            "ts": int(event.timestamp.timestamp())
        }
        
        return {"attachments": [attachment]}
    
    def _format_discord_message(self, event: Event) -> Dict[str, Any]:
        """Format message for Discord webhook."""
        color_map = {
            "card.created": 0x2ECC71,  # Green
            "card.moved": 0x3498DB,    # Blue
            "card.updated": 0xF39C12,  # Orange
            "card.deleted": 0xE74C3C,  # Red
            "board.created": 0x9B59B6,  # Purple
            "comment.added": 0x1ABC9C   # Turquoise
        }
        
        color = color_map.get(event.type, 0x95A5A6)  # Default gray
        
        # Build embed based on event type
        embed = {
            "color": color,
            "timestamp": event.timestamp.isoformat(),
            "footer": {"text": "Kanban Bot"}
        }
        
        if event.type == "card.created":
            card = event.data["card"]
            embed["title"] = "New Card Created"
            embed["description"] = f"**{card.title}**"
            embed["fields"] = [
                {"name": "Board", "value": event.data.get("board_name", "Unknown"), "inline": True},
                {"name": "Column", "value": card.column, "inline": True}
            ]
            if card.assignee:
                embed["fields"].append({"name": "Assignee", "value": card.assignee, "inline": True})
                
        elif event.type == "card.moved":
            card = event.data["card"]
            embed["title"] = "Card Moved"
            embed["description"] = f"**{card.title}**"
            embed["fields"] = [
                {"name": "From", "value": event.data["from_column"], "inline": True},
                {"name": "To", "value": event.data["to_column"], "inline": True}
            ]
            
        elif event.type == "comment.added":
            comment = event.data["comment"]
            embed["title"] = "New Comment"
            embed["description"] = comment.text
            embed["fields"] = [
                {"name": "Card", "value": event.data.get("card_title", "Unknown"), "inline": True},
                {"name": "Author", "value": comment.author, "inline": True}
            ]
        
        else:
            embed["title"] = f"Event: {event.type}"
            embed["description"] = "A kanban event occurred"
        
        return {"embeds": [embed]}
    
    def _format_teams_message(self, event: Event) -> Dict[str, Any]:
        """Format message for Microsoft Teams webhook."""
        # Build adaptive card for Teams
        card = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": f"Kanban event: {event.type}",
            "sections": []
        }
        
        if event.type == "card.created":
            card_obj = event.data["card"]
            card["title"] = "New Card Created"
            card["sections"].append({
                "activityTitle": card_obj.title,
                "facts": [
                    {"name": "Board", "value": event.data.get("board_name", "Unknown")},
                    {"name": "Column", "value": card_obj.column}
                ]
            })
            
        elif event.type == "card.moved":
            card_obj = event.data["card"]
            card["title"] = "Card Moved"
            card["sections"].append({
                "activityTitle": card_obj.title,
                "facts": [
                    {"name": "From", "value": event.data["from_column"]},
                    {"name": "To", "value": event.data["to_column"]}
                ]
            })
        
        else:
            card["title"] = f"Event: {event.type}"
            card["text"] = "A kanban event occurred"
        
        return card
    
    def _format_generic_message(self, event: Event) -> Dict[str, Any]:
        """Format message for generic webhook."""
        return {
            "event_type": event.type,
            "timestamp": event.timestamp.isoformat(),
            "user_id": event.user_id,
            "board_id": event.board_id,
            "data": event.data
        }


class RateLimitedNotifier(WebhookNotifier):
    """Webhook notifier with rate limiting to prevent spam."""
    
    def __init__(self, configs: List[WebhookConfig], 
                 rate_limit_window: int = 60,  # seconds
                 max_events_per_window: int = 10):
        super().__init__(configs)
        self.rate_limit_window = rate_limit_window
        self.max_events_per_window = max_events_per_window
        self.event_history: Dict[str, List[float]] = {}
    
    def handle(self, event: Event) -> None:
        """Handle event with rate limiting."""
        # Check rate limit
        key = f"{event.board_id}:{event.type}"
        now = datetime.utcnow().timestamp()
        
        if key not in self.event_history:
            self.event_history[key] = []
        
        # Remove old events outside the window
        cutoff = now - self.rate_limit_window
        self.event_history[key] = [
            ts for ts in self.event_history[key] 
            if ts > cutoff
        ]
        
        # Check if we're over the limit
        if len(self.event_history[key]) >= self.max_events_per_window:
            print(f"Rate limit exceeded for {key}, skipping notification")
            return
        
        # Record this event
        self.event_history[key].append(now)
        
        # Send notification
        super().handle(event)


def demo_webhook_notifications():
    """Demonstrate webhook notifications."""
    print("=== Webhook Notifications Demo ===\n")
    
    # Create webhook configurations
    # Note: These are example URLs - replace with real ones for testing
    configs = [
        WebhookConfig(
            url="https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK",
            type=WebhookType.SLACK,
            events=["card.*", "comment.added"]  # All card events and comments
        ),
        WebhookConfig(
            url="https://discord.com/api/webhooks/YOUR/DISCORD/WEBHOOK",
            type=WebhookType.DISCORD,
            events=["card.moved", "card.created"]  # Specific events
        ),
        WebhookConfig(
            url="https://your-app.com/webhooks/kanban",
            type=WebhookType.GENERIC,
            events=["*"],  # All events
            headers={"Authorization": "Bearer YOUR_TOKEN"}
        )
    ]
    
    # Create notifier with rate limiting
    notifier = RateLimitedNotifier(
        configs,
        rate_limit_window=60,
        max_events_per_window=5
    )
    
    # Create kanban with notification handler
    kanban = SimpleKanban()
    kanban.event_bus.subscribe("*", notifier)
    
    # Also add console logging for demo
    def log_event(event: Event):
        print(f"[{event.timestamp.strftime('%H:%M:%S')}] {event.type}: ", end="")
        if "card" in event.data:
            print(f"{event.data['card'].title}")
        elif "board" in event.data:
            print(f"{event.data['board'].name}")
        else:
            print("Event triggered")
    
    kanban.event_bus.subscribe("*", log_event)
    
    # Create a board and demonstrate notifications
    print("Creating board and triggering events...\n")
    
    board = kanban.create_board("demo_user", "Webhook Demo Project")
    
    # Create cards
    card1 = kanban.add_card(
        "demo_user",
        board.id,
        "To Do",
        "Setup webhook integration",
        description="Configure Slack and Discord webhooks",
        assignee="developer1"
    )
    
    card2 = kanban.add_card(
        "demo_user",
        board.id,
        "To Do",
        "Test notifications",
        labels=["testing", "integration"]
    )
    
    # Move cards
    kanban.move_card("demo_user", board.id, card1.id, "In Progress")
    
    # Update card
    kanban.update_card(
        "demo_user",
        board.id,
        card2.id,
        assignee="tester1",
        labels=["testing", "integration", "priority:high"]
    )
    
    # Add comment
    kanban.add_comment(
        "demo_user",
        board.id,
        card1.id,
        "Webhook endpoints configured and ready for testing"
    )
    
    # Demonstrate rate limiting
    print("\n\nDemonstrating rate limiting...")
    print("Creating multiple cards quickly...\n")
    
    for i in range(7):
        kanban.add_card(
            "demo_user",
            board.id,
            "To Do",
            f"Task {i + 1}"
        )
    
    print("\n\nDemo complete!")
    print("\nTo test with real webhooks:")
    print("1. Replace the webhook URLs in the configs list")
    print("2. Run this script")
    print("3. Check your Slack/Discord channels for notifications")
    
    # Example of creating a test endpoint
    print("\n\nExample test webhook server (Python):")
    print("""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import json
    
    class WebhookHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)
            
            print(f"Received webhook: {json.dumps(data, indent=2)}")
            
            self.send_response(200)
            self.end_headers()
    
    server = HTTPServer(('localhost', 8080), WebhookHandler)
    print("Webhook server listening on http://localhost:8080")
    server.serve_forever()
    """)


if __name__ == "__main__":
    demo_webhook_notifications()