"""Tests for event system components."""

import threading
import time
from datetime import datetime, timedelta, timezone
from enum import Enum
from unittest.mock import Mock

import pytest

from kanban import Event, EventBus, EventRegistry


class TestEventRegistry:
    """Test EventRegistry functionality."""

    def test_event_registry_creation(self):
        """Test creating event registry with builtin events."""
        builtin = {"test.event": "Test event description"}
        registry = EventRegistry(builtin)
        
        assert "test.event" in registry
        assert registry._events["test.event"] == "Test event description"

    def test_event_registry_register_new_event(self):
        """Test registering a new event."""
        registry = EventRegistry()
        
        registry.register("custom.event", "Custom event description")
        
        assert "custom.event" in registry
        assert registry._events["custom.event"] == "Custom event description"

    def test_event_registry_register_duplicate_event(self):
        """Test registering duplicate event raises error."""
        registry = EventRegistry()
        
        registry.register("duplicate.event", "First registration")
        
        with pytest.raises(ValueError, match="Event 'duplicate.event' already registered"):
            registry.register("duplicate.event", "Second registration")

    def test_event_registry_contains(self):
        """Test event registry containment check."""
        registry = EventRegistry({"existing.event": "Description"})
        
        assert "existing.event" in registry
        assert "nonexistent.event" not in registry

    def test_event_registry_iteration(self):
        """Test iterating over event registry."""
        events = {"event1": "Desc1", "event2": "Desc2", "event3": "Desc3"}
        registry = EventRegistry(events)
        
        registered_events = list(registry)
        assert set(registered_events) == {"event1", "event2", "event3"}


class SampleEnum(Enum):
    """Sample enum for testing serialization."""
    OPTION_A = "a"
    OPTION_B = "b"


class TestEvent:
    """Test Event model and serialization."""

    def test_event_creation(self):
        """Test basic event creation."""
        now = datetime.now(timezone.utc)
        event = Event(
            type="test.event",
            entity_id="entity1",
            entity_type="test",
            id="event1",
            timestamp=now,
            data={"key": "value"},
            user_id="user1"
        )
        
        assert event.type == "test.event"
        assert event.entity_id == "entity1"
        assert event.entity_type == "test"
        assert event.id == "event1"
        assert event.timestamp == now
        assert event.data == {"key": "value"}
        assert event.user_id == "user1"

    def test_event_to_dict_basic(self):
        """Test event serialization to dictionary."""
        now = datetime.now(timezone.utc)
        event = Event(
            type="test.event",
            entity_id="entity1",
            entity_type="test",
            id="event1",
            timestamp=now,
            data={"simple": "value"},
            user_id="user1"
        )
        
        result = event.to_dict()
        
        assert result["type"] == "test.event"
        assert result["entity_id"] == "entity1"
        assert result["entity_type"] == "test"
        assert result["id"] == "event1"
        assert result["timestamp"] == now.isoformat()
        assert result["user_id"] == "user1"
        assert result["data"]["simple"] == "value"

    def test_event_to_dict_set_serialization(self):
        """Test event serialization with set values."""
        event = Event(
            type="test.event",
            entity_id="entity1",
            entity_type="test",
            id="event1",
            timestamp=datetime.now(timezone.utc),
            data={"tags": {"tag1", "tag3", "tag2"}}
        )
        
        result = event.to_dict()
        
        # Sets should be converted to sorted lists
        assert result["data"]["tags"] == ["tag1", "tag2", "tag3"]

    def test_event_to_dict_datetime_serialization(self):
        """Test event serialization with datetime values."""
        now = datetime.now(timezone.utc)
        event = Event(
            type="test.event",
            entity_id="entity1",
            entity_type="test",
            id="event1",
            timestamp=now,
            data={"created_at": now}
        )
        
        result = event.to_dict()
        
        assert result["data"]["created_at"] == now.isoformat()

    def test_event_to_dict_timedelta_serialization(self):
        """Test event serialization with timedelta values."""
        duration = timedelta(hours=2, minutes=30)
        event = Event(
            type="test.event",
            entity_id="entity1",
            entity_type="test",
            id="event1",
            timestamp=datetime.now(timezone.utc),
            data={"duration": duration}
        )
        
        result = event.to_dict()
        
        assert result["data"]["duration"] == duration.total_seconds()

    def test_event_to_dict_enum_serialization(self):
        """Test event serialization with enum values."""
        event = Event(
            type="test.event",
            entity_id="entity1",
            entity_type="test",
            id="event1",
            timestamp=datetime.now(timezone.utc),
            data={"option": SampleEnum.OPTION_A}
        )
        
        result = event.to_dict()
        
        assert result["data"]["option"] == "a"

    def test_event_to_dict_complex_nested_data(self):
        """Test event serialization with complex nested data structures."""
        now = datetime.now(timezone.utc)
        duration = timedelta(minutes=15)
        
        event = Event(
            type="test.event",
            entity_id="entity1",
            entity_type="test",
            id="event1",
            timestamp=now,
            data={
                "metadata": {
                    "tags": {"urgent", "review"},
                    "created": now,
                    "duration": duration,
                    "status": SampleEnum.OPTION_B
                },
                "simple_value": "test"
            }
        )
        
        result = event.to_dict()
        
        # Sets are converted to sorted lists, but we need to handle nested serialization
        # The event.to_dict() method doesn't recursively serialize nested dictionaries
        # Only the top-level data items are serialized
        assert isinstance(result["data"]["metadata"]["tags"], set)
        assert result["data"]["metadata"]["created"] == now.isoformat()
        assert result["data"]["metadata"]["duration"] == duration.total_seconds()
        assert result["data"]["metadata"]["status"] == "b"
        assert result["data"]["simple_value"] == "test"


class TestEventBus:
    """Test EventBus functionality."""

    def test_event_bus_creation(self):
        """Test creating event bus."""
        bus = EventBus()
        assert bus._subscriptions == {}
        assert len(bus._events) == 0

    def test_event_bus_creation_with_max_size(self):
        """Test creating event bus with custom max size."""
        bus = EventBus(max_size=100)
        assert bus._events.maxlen == 100

    def test_subscribe_and_publish(self):
        """Test subscribing to events and publishing."""
        bus = EventBus()
        handler = Mock()
        
        bus.subscribe("test.event", handler)
        
        event = Event(
            type="test.event",
            entity_id="entity1",
            entity_type="test",
            id="event1",
            timestamp=datetime.now(timezone.utc)
        )
        
        bus.publish(event)
        
        handler.assert_called_once_with(event)

    def test_subscribe_multiple_handlers(self):
        """Test multiple handlers for same event."""
        bus = EventBus()
        handler1 = Mock()
        handler2 = Mock()
        
        bus.subscribe("test.event", handler1)
        bus.subscribe("test.event", handler2)
        
        event = Event(
            type="test.event",
            entity_id="entity1",
            entity_type="test",
            id="event1",
            timestamp=datetime.now(timezone.utc)
        )
        
        bus.publish(event)
        
        handler1.assert_called_once_with(event)
        handler2.assert_called_once_with(event)

    def test_wildcard_subscription(self):
        """Test wildcard subscription receives all events."""
        bus = EventBus()
        wildcard_handler = Mock()
        specific_handler = Mock()
        
        bus.subscribe("*", wildcard_handler)
        bus.subscribe("specific.event", specific_handler)
        
        event1 = Event(
            type="specific.event",
            entity_id="entity1",
            entity_type="test",
            id="event1",
            timestamp=datetime.now(timezone.utc)
        )
        
        event2 = Event(
            type="other.event",
            entity_id="entity2",
            entity_type="test",
            id="event2",
            timestamp=datetime.now(timezone.utc)
        )
        
        bus.publish(event1)
        bus.publish(event2)
        
        # Wildcard handler should receive both events
        assert wildcard_handler.call_count == 2
        wildcard_handler.assert_any_call(event1)
        wildcard_handler.assert_any_call(event2)
        
        # Specific handler should only receive specific event
        specific_handler.assert_called_once_with(event1)

    def test_unsubscribe(self):
        """Test unsubscribing from events."""
        bus = EventBus()
        handler = Mock()
        
        bus.subscribe("test.event", handler)
        bus.unsubscribe("test.event", handler)
        
        event = Event(
            type="test.event",
            entity_id="entity1",
            entity_type="test",
            id="event1",
            timestamp=datetime.now(timezone.utc)
        )
        
        bus.publish(event)
        
        handler.assert_not_called()

    def test_unsubscribe_nonexistent_handler(self):
        """Test unsubscribing handler that wasn't subscribed."""
        bus = EventBus()
        handler = Mock()
        
        # Should not raise error
        bus.unsubscribe("nonexistent.event", handler)

    def test_handler_exception_handling(self):
        """Test that handler exceptions are logged but don't stop other handlers."""
        bus = EventBus()
        
        failing_handler = Mock(side_effect=Exception("Handler failed"))
        working_handler = Mock()
        
        bus.subscribe("test.event", failing_handler)
        bus.subscribe("test.event", working_handler)
        
        event = Event(
            type="test.event",
            entity_id="entity1",
            entity_type="test",
            id="event1",
            timestamp=datetime.now(timezone.utc)
        )
        
        # Should not raise exception despite failing handler
        bus.publish(event)
        
        failing_handler.assert_called_once_with(event)
        working_handler.assert_called_once_with(event)

    def test_event_retention(self):
        """Test that events are retained in history."""
        bus = EventBus()
        
        event1 = Event(
            type="test.event1",
            entity_id="entity1",
            entity_type="test",
            id="event1",
            timestamp=datetime.now(timezone.utc)
        )
        
        event2 = Event(
            type="test.event2",
            entity_id="entity2",
            entity_type="test",
            id="event2",
            timestamp=datetime.now(timezone.utc)
        )
        
        bus.publish(event1)
        bus.publish(event2)
        
        events = bus.get_events()
        assert len(events) == 2
        assert event1 in events
        assert event2 in events

    def test_get_events_with_since_filter(self):
        """Test filtering events by timestamp."""
        bus = EventBus()
        
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        recent_time = datetime.now(timezone.utc) - timedelta(minutes=30)
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)
        
        old_event = Event(
            type="old.event",
            entity_id="entity1",
            entity_type="test",
            id="event1",
            timestamp=old_time
        )
        
        recent_event = Event(
            type="recent.event",
            entity_id="entity2",
            entity_type="test",
            id="event2",
            timestamp=recent_time
        )
        
        bus.publish(old_event)
        bus.publish(recent_event)
        
        # Get events since cutoff time
        filtered_events = bus.get_events(since=cutoff_time)
        
        assert len(filtered_events) == 1
        assert recent_event in filtered_events
        assert old_event not in filtered_events

    def test_max_event_size_limit(self):
        """Test event deque respects max size limit."""
        bus = EventBus(max_size=2)
        
        # Publish 3 events
        for i in range(3):
            event = Event(
                type=f"test.event{i}",
                entity_id=f"entity{i}",
                entity_type="test",
                id=f"event{i}",
                timestamp=datetime.now(timezone.utc)
            )
            bus.publish(event)
        
        # Should only retain last 2 events
        events = bus.get_events()
        assert len(events) == 2
        
        # Should be the last two events
        event_types = [e.type for e in events]
        assert "test.event1" in event_types
        assert "test.event2" in event_types
        assert "test.event0" not in event_types

    def test_thread_safety(self):
        """Test that EventBus operations are thread-safe."""
        bus = EventBus()
        handler = Mock()
        bus.subscribe("test.event", handler)
        
        def publish_events(thread_id):
            for i in range(10):
                event = Event(
                    type="test.event",
                    entity_id=f"entity-{thread_id}-{i}",
                    entity_type="test",
                    id=f"event-{thread_id}-{i}",
                    timestamp=datetime.now(timezone.utc)
                )
                bus.publish(event)
                time.sleep(0.001)  # Small delay
        
        # Start multiple threads publishing events
        threads = []
        for i in range(3):
            thread = threading.Thread(target=publish_events, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All events should have been processed
        assert handler.call_count == 30
        
        # All events should be in history
        events = bus.get_events()
        assert len(events) == 30