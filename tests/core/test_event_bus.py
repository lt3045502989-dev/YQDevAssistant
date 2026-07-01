"""
Tests for src.core.event_bus — the pub/sub system.
"""

import pytest
from src.core.event_bus import EventBus


class TestEventBus:
    """Tests for the EventBus publish/subscribe system."""

    def test_subscribe_and_receive(self, event_bus):
        """A subscribed handler receives published events."""
        received = []

        def handler(event_name, data):
            received.append((event_name, data))

        event_bus.subscribe("test:event", handler)
        event_bus.publish("test:event", {"key": "value"})

        assert len(received) == 1
        assert received[0] == ("test:event", {"key": "value"})

    def test_exact_match_only(self, event_bus):
        """
        Without wildcards, only exact matches are delivered.

        Publishing "other:event" does NOT trigger a "test:event" subscription.
        """
        received = []

        event_bus.subscribe("test:event", lambda n, d: received.append(n))
        event_bus.publish("other:event")

        assert len(received) == 0

    def test_wildcard_star_matches_everything(self, event_bus):
        """'*' in a pattern matches any sequence of characters."""
        received = []

        event_bus.subscribe("github:*", lambda n, d: received.append(n))

        event_bus.publish("github:repo_cloned")
        event_bus.publish("github:issue_created")
        event_bus.publish("github:pr:merged")  # '*' matches anything after 'github:'

        assert len(received) == 3
        assert "github:repo_cloned" in received
        assert "github:pr:merged" in received

    def test_wildcard_question_matches_one(self, event_bus):
        """'?' in a pattern matches exactly one character."""
        received = []

        event_bus.subscribe("task:??", lambda n, d: received.append(n))

        event_bus.publish("task:ab")  # matches (2 chars after ':')
        event_bus.publish("task:abc")  # does NOT match (3 chars)
        event_bus.publish("task:a")  # does NOT match (1 char)

        assert len(received) == 1
        assert received[0] == "task:ab"

    def test_multiple_subscribers_same_pattern(self, event_bus):
        """Multiple handlers can subscribe to the same pattern."""
        r1, r2 = [], []

        event_bus.subscribe("test:*", lambda n, d: r1.append(n))
        event_bus.subscribe("test:*", lambda n, d: r2.append(n))
        event_bus.publish("test:something")

        assert len(r1) == 1
        assert len(r2) == 1

    def test_multiple_patterns_same_handler(self, event_bus):
        """The same handler can subscribe to multiple patterns."""
        received = []

        def handler(n, d):
            received.append(n)

        event_bus.subscribe("a:*", handler)
        event_bus.subscribe("b:*", handler)
        event_bus.publish("a:1")
        event_bus.publish("b:1")

        assert len(received) == 2

    def test_unsubscribe_removes_handler(self, event_bus):
        """After unsubscribe, the handler no longer receives events."""
        received = []

        def handler(n, d):
            received.append(n)

        event_bus.subscribe("test:*", handler)
        event_bus.unsubscribe("test:*", handler)
        event_bus.publish("test:something")

        assert len(received) == 0

    def test_unsubscribe_nonexistent_raises(self, event_bus):
        """Unsubscribing from a pattern with no subscribers raises ValueError."""
        with pytest.raises(ValueError):
            event_bus.unsubscribe("nonexistent", lambda n, d: None)

    def test_unsubscribe_wrong_pattern_raises(self, event_bus):
        """Unsubscribing a handler from the wrong pattern raises ValueError."""

        def handler(n, d):
            pass

        event_bus.subscribe("a:*", handler)
        with pytest.raises(ValueError):
            event_bus.unsubscribe("b:*", handler)

    def test_error_isolation(self, event_bus):
        """
        If one handler crashes, other handlers still run.

        This is CRITICAL: a buggy module's event handler must not
        break other modules' handlers.
        """
        r1, r2 = [], []

        def crashy(n, d):
            raise RuntimeError("BOOM!")

        def survivor(n, d):
            r2.append(n)

        event_bus.subscribe("test:*", crashy)
        event_bus.subscribe("test:*", survivor)
        event_bus.publish("test:event")

        # crashy crashed, but survivor still ran
        assert len(r2) == 1
        assert r2[0] == "test:event"

    def test_clear_removes_all(self, event_bus):
        """clear() removes all subscribers."""
        received = []

        event_bus.subscribe("a:*", lambda n, d: received.append(n))
        event_bus.subscribe("b:*", lambda n, d: received.append(n))
        event_bus.clear()

        event_bus.publish("a:something")
        event_bus.publish("b:something")

        assert len(received) == 0

    def test_subscriber_count(self, event_bus):
        """subscriber_count tracks registrations correctly."""
        assert event_bus.subscriber_count == 0

        event_bus.subscribe("a:*", lambda n, d: None)
        assert event_bus.subscriber_count == 1

        event_bus.subscribe("b:*", lambda n, d: None)
        assert event_bus.subscriber_count == 2

        # Same handler, different pattern = counts as 2
        h = lambda n, d: None
        event_bus.subscribe("c:*", h)
        event_bus.subscribe("d:*", h)
        assert event_bus.subscriber_count == 4

    def test_publish_with_no_subscribers(self, event_bus):
        """Publishing with no subscribers is harmless (no-op)."""
        # Should not raise
        event_bus.publish("nobody:cares")

    def test_non_callable_handler_raises(self, event_bus):
        """Subscribing a non-callable raises TypeError."""
        with pytest.raises(TypeError):
            event_bus.subscribe("test:*", "not a function")

    def test_handler_receives_empty_dict_by_default(self, event_bus):
        """If no data is passed to publish, handler receives empty dict."""
        captured = {}

        def handler(n, d):
            captured["data"] = d

        event_bus.subscribe("test:*", handler)
        event_bus.publish("test:event")

        assert captured["data"] == {}
