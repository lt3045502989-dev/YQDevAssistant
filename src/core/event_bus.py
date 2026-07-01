"""
YQ Dev Assistant — Event Bus.

A simple publish/subscribe system for inter-module communication.
Modules publish events; other modules subscribe to patterns and
are notified when matching events occur.

Design principles:
    1. DECOUPLING: Publishers don't know who is listening.
       Subscribers don't know who is publishing.
       Both only know about the event name.

    2. ERROR ISOLATION: If one handler crashes, other handlers
       still run. The publisher is never affected by broken subscribers.
       (Like a radio broadcast — one broken radio doesn't stop the broadcast.)

    3. WILDCARD MATCHING: Subscribers use fnmatch patterns.
       - "github:*" matches "github:repo_cloned", "github:issue_created", etc.
       - "*:completed" matches "health:completed", "backup:completed", etc.
       - "module:??_failed" matches "module:ab_failed" but not "module:abc_failed"

    4. SYNCHRONOUS: Handlers run in the publishing thread, in subscription order.
       (No async complexity in M1.1 — we add async later if needed.)

Usage:
    >>> bus = EventBus()
    >>> bus.subscribe("module:*", my_handler)
    >>> bus.publish("module:started", {"name": "health"})
    >>> bus.unsubscribe("module:*", my_handler)
    >>> bus.clear()  # Remove all subscribers
"""

import fnmatch
import logging
from collections import defaultdict
from collections.abc import Callable
from threading import Lock
from typing import Any

# EventHandler signature: (event_name: str, data: dict) -> None
EventHandler = Callable[[str, dict[str, Any]], None]

logger = logging.getLogger(__name__)


class EventBus:
    """
    Simple pub/sub event bus with fnmatch wildcard pattern matching.

    Thread-safe: subscribe/unsubscribe acquire a lock.
    Publish iterates a snapshot to avoid holding the lock
    during handler execution (preventing deadlocks if a
    handler calls subscribe/unsubscribe).

    Examples:
        >>> bus = EventBus()

        # Subscribe to all module events
        >>> results = []
        >>> bus.subscribe("module:*", lambda name, data: results.append(name))

        # Publish triggers the handler
        >>> bus.publish("module:started", {"name": "health"})
        >>> results
        ['module:started']
    """

    def __init__(self) -> None:
        # Each pattern can have multiple handlers.
        # defaultdict(list) means: bus.subscribe("x", h) works even
        # if "x" has never been subscribed before.
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._lock = Lock()

    # ── Subscribe ──────────────────────────────────────

    def subscribe(self, pattern: str, handler: EventHandler) -> None:
        """
        Register a handler for events matching the pattern.

        The same handler can be subscribed to multiple patterns.
        The same handler can be subscribed to the same pattern
        multiple times (it will be called multiple times).

        Args:
            pattern: fnmatch pattern (e.g., "github:*", "*:completed").
            handler: Callable that takes (event_name, data).

        Raises:
            TypeError: If handler is not callable.
        """
        if not callable(handler):
            raise TypeError(f"Handler must be callable, got {type(handler).__name__}")

        with self._lock:
            self._subscribers[pattern].append(handler)
            logger.debug(
                "Subscribed handler to pattern '%s' (now %d handler(s))",
                pattern,
                len(self._subscribers[pattern]),
            )

    # ── Unsubscribe ────────────────────────────────────

    def unsubscribe(self, pattern: str, handler: EventHandler) -> None:
        """
        Remove a specific handler from a pattern.

        Raises:
            ValueError: If the handler is not found for this pattern.
        """
        with self._lock:
            if pattern not in self._subscribers:
                raise ValueError(
                    f"No subscribers for pattern '{pattern}'"
                )
            try:
                self._subscribers[pattern].remove(handler)
                logger.debug(
                    "Unsubscribed handler from pattern '%s' (now %d handler(s))",
                    pattern,
                    len(self._subscribers[pattern]),
                )
                # Clean up empty pattern entries
                if not self._subscribers[pattern]:
                    del self._subscribers[pattern]
            except ValueError:
                raise ValueError(
                    f"Handler not found for pattern '{pattern}'"
                ) from None

    # ── Publish ────────────────────────────────────────

    def publish(self, event_name: str, data: dict[str, Any] | None = None) -> None:
        """
        Publish an event to all matching subscribers.

        The event is delivered to every handler whose pattern
        matches the event_name (using fnmatch).

        If a handler raises an exception, the error is logged
        and remaining handlers still execute.

        Args:
            event_name: The event identifier (e.g., "module:started").
            data: Optional payload dictionary. Defaults to empty dict.
        """
        data = data or {}

        # Take a snapshot of subscribers under the lock,
        # then release before calling handlers.
        # This prevents deadlocks if a handler calls
        # subscribe() or unsubscribe().
        with self._lock:
            snapshot = list(self._subscribers.items())

        matched = 0
        for pattern, handlers in snapshot:
            if fnmatch.fnmatch(event_name, pattern):
                for handler in handlers:
                    try:
                        handler(event_name, data)
                        matched += 1
                    except Exception:
                        # Error isolation: one broken handler must not
                        # prevent other handlers from running.
                        logger.exception(
                            "Handler for pattern '%s' raised an exception "
                            "while processing event '%s'",
                            pattern,
                            event_name,
                        )

        if matched == 0:
            logger.debug(
                "Event '%s' published but no subscribers matched", event_name
            )
        else:
            logger.debug(
                "Event '%s' delivered to %d handler(s)", event_name, matched
            )

    # ── Clear ──────────────────────────────────────────

    def clear(self) -> None:
        """
        Remove ALL subscribers.

        Useful for test teardown — ensures a clean slate
        between test cases.
        """
        with self._lock:
            count = sum(len(h) for h in self._subscribers.values())
            self._subscribers.clear()
            logger.debug("Cleared all subscribers (%d total)", count)

    # ── Properties ─────────────────────────────────────

    @property
    def subscriber_count(self) -> int:
        """
        Total number of handler registrations.

        Note: This counts registrations, not unique handlers.
        The same handler subscribed to 3 patterns counts as 3.

        Returns:
            Total number of (pattern, handler) pairs.
        """
        with self._lock:
            return sum(len(handlers) for handlers in self._subscribers.values())

    @property
    def pattern_count(self) -> int:
        """
        Number of unique patterns with active subscribers.

        Returns:
            Count of unique patterns.
        """
        with self._lock:
            return len(self._subscribers)

    def __repr__(self) -> str:
        return f"EventBus(subscribers={self.subscriber_count}, patterns={self.pattern_count})"
