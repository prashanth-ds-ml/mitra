"""Internal event bus for CodeMitra hooks system."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
from collections import defaultdict
import threading


@dataclass(frozen=True)
class HookContext:
    """Context passed to hook handlers."""
    workspace: str
    session_mode: str
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PreToolEvent:
    """Event fired before a tool is executed."""
    tool_name: str
    tool_args: dict
    request: str
    context: HookContext


@dataclass(frozen=True)
class PostToolEvent:
    """Event fired after a tool completes."""
    tool_name: str
    tool_args: dict
    result: Any
    context: HookContext
    error: str | None = None


@dataclass(frozen=True)
class SessionStartEvent:
    """Event fired when a new session starts."""
    workspace: str
    session_mode: str
    model: str
    context: HookContext


@dataclass(frozen=True)
class SessionEndEvent:
    """Event fired when a session ends."""
    workspace: str
    session_mode: str
    total_tokens: int
    message_count: int
    context: HookContext


@dataclass(frozen=True)
class CompactCompleteEvent:
    """Event fired after context compaction completes."""
    workspace: str
    reason: str
    tokens_before: int
    tokens_after: int
    messages_removed: int
    context: HookContext


Event = (
    PreToolEvent
    | PostToolEvent
    | SessionStartEvent
    | SessionEndEvent
    | CompactCompleteEvent
)

Handler = Callable[[Event], None]


class EventBus:
    """Thread-safe event bus for hook dispatching."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._lock = threading.RLock()

    def subscribe(self, event_type: str, handler: Handler) -> None:
        """Register a handler for an event type."""
        with self._lock:
            self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Handler) -> None:
        """Unregister a handler."""
        with self._lock:
            if handler in self._handlers[event_type]:
                self._handlers[event_type].remove(handler)

    def emit(self, event: Event) -> None:
        """Emit an event to all registered handlers."""
        event_type = type(event).__name__
        with self._lock:
            handlers = list(self._handlers.get(event_type, []))
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                pass

    def clear(self) -> None:
        """Clear all handlers."""
        with self._lock:
            self._handlers.clear()


_global_bus = EventBus()


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    return _global_bus


def emit(event: Event) -> None:
    """Emit an event on the global bus."""
    _global_bus.emit(event)


def on(event_type: str, handler: Handler) -> None:
    """Register a handler on the global bus."""
    _global_bus.subscribe(event_type, handler)


def off(event_type: str, handler: Handler) -> None:
    """Unregister a handler from the global bus."""
    _global_bus.unsubscribe(event_type, handler)