"""
binterint.event_bus
===================
Central pub/sub event system for binterint's modular plugin architecture.

The event bus follows the microkernel pattern: every component is a
:class:`TerminalPlugin` that registers with a single :class:`EventBus` and
communicates exclusively via :class:`Event` objects.  No component holds a
direct reference to another.

Example
-------
    from binterint.event_bus import EventBus, Event, EventType

    bus = EventBus()

    class PrintPlugin(TerminalPlugin):
        @property
        def name(self): return "printer"
        def subscribe_to(self): return [EventType.PTY_DATA]
        def on_register(self, bus): self._bus = bus
        def on_event(self, event):
            print("received:", event.data)
        def on_unregister(self): pass

    bus.register(PrintPlugin())
    bus.emit(Event(EventType.PTY_DATA, "test", {"text": "hello"}))
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("binterint.event_bus")


# ---------------------------------------------------------------------------
# EventType enum
# ---------------------------------------------------------------------------

class EventType(Enum):
    """All event types that can flow through the :class:`EventBus`."""

    # PTY / process lifecycle
    PTY_DATA   = auto()  #: Raw text received from the PTY
    PTY_CLOSED = auto()  #: Child process exited
    PTY_RESIZED = auto() #: Terminal dimensions changed

    # Screen / buffer
    SCREEN_UPDATED  = auto()  #: Screen buffer changed (full repaint)
    SCREEN_DIRTY_RECT = auto() #: Incremental bounding box of changed cells
    CURSOR_MOVED    = auto()  #: Cursor position changed

    # User input
    KEY_PRESS   = auto()  #: Keyboard key was pressed
    KEY_RELEASE = auto()  #: Keyboard key was released (where supported)
    MOUSE_EVENT = auto()  #: Mouse click, drag, or scroll
    PASTE_EVENT = auto()  #: Clipboard paste received

    # Render
    RENDER_FRAME    = auto()  #: A new frame should be rendered
    RENDER_COMPLETE = auto()  #: A frame was successfully rendered

    # Semantic analysis
    ELEMENT_DETECTED   = auto()  #: A UI element was found in the screen
    ELEMENT_INTERACTED = auto()  #: An element was activated (click/key)

    # Lifecycle
    PLUGIN_LOADED   = auto()  #: A plugin was registered with the bus
    PLUGIN_UNLOADED = auto()  #: A plugin was removed from the bus
    SHUTDOWN        = auto()  #: The system is shutting down


# ---------------------------------------------------------------------------
# Event dataclass
# ---------------------------------------------------------------------------

@dataclass
class Event:
    """An event flowing through the :class:`EventBus`.

    Args:
        type: The :class:`EventType` identifying this event.
        source: Name of the plugin that emitted the event.
        data: Arbitrary payload dictionary (optional).
        timestamp: Unix timestamp of creation (set automatically).
        propagation_stopped: Set to ``True`` inside :meth:`TerminalPlugin.on_event`
            to prevent subsequent subscribers from receiving this event.
    """
    type:                EventType
    source:              str
    data:                Dict[str, Any] = field(default_factory=dict)
    timestamp:           float         = field(default_factory=time.time)
    propagation_stopped: bool          = False


# ---------------------------------------------------------------------------
# TerminalPlugin ABC
# ---------------------------------------------------------------------------

class TerminalPlugin(ABC):
    """Abstract base class for all binterint plugin components.

    Subclasses must implement :meth:`name`, :meth:`on_register`,
    :meth:`on_event`, and :meth:`on_unregister`.  Override
    :meth:`subscribe_to` to declare which :class:`EventType`\\s the plugin
    wants to receive.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique plugin identifier (used as routing key in the bus)."""

    @abstractmethod
    def on_register(self, bus: "EventBus") -> None:
        """Called immediately after the plugin is registered with the bus.

        Args:
            bus: The :class:`EventBus` instance this plugin belongs to.
        """

    @abstractmethod
    def on_event(self, event: Event) -> None:
        """Handle an inbound event.

        Args:
            event: The :class:`Event` routed to this plugin.  Set
                ``event.propagation_stopped = True`` to prevent delivery to
                later subscribers.
        """

    @abstractmethod
    def on_unregister(self) -> None:
        """Called when the plugin is removed from the bus.  Release resources here."""

    def subscribe_to(self) -> List[EventType]:
        """Return the list of :class:`EventType`\\s this plugin listens to.

        Override in subclasses.  Default is an empty list (no subscriptions).
        """
        return []


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------

class EventBus:
    """Central publish/subscribe event dispatcher for binterint.

    Plugins register with the bus and declare their subscriptions.  When
    :meth:`emit` is called the bus routes the event to every subscribed plugin
    in registration order, respecting ``event.propagation_stopped``.

    An ordered event history is kept for debugging and replay.
    """

    def __init__(self, *, max_history: int = 1000) -> None:
        """
        Args:
            max_history: Maximum number of events to keep in the history buffer.
        """
        self._subscribers:    Dict[EventType, List[TerminalPlugin]] = defaultdict(list)
        self._plugins:        Dict[str, TerminalPlugin]             = {}
        self._event_history:  List[Event]                           = []
        self._hooks:          Dict[str, List[Callable]]             = defaultdict(list)
        self._max_history:    int                                    = max_history

    # ------------------------------------------------------------------
    # Plugin registration
    # ------------------------------------------------------------------

    def register(self, plugin: TerminalPlugin) -> None:
        """Register a plugin and subscribe it to its declared event types.

        Args:
            plugin: The plugin to register.

        Raises:
            ValueError: If a plugin with the same name is already registered.
        """
        if plugin.name in self._plugins:
            raise ValueError(f"Plugin '{plugin.name}' is already registered")

        self._plugins[plugin.name] = plugin
        for event_type in plugin.subscribe_to():
            self._subscribers[event_type].append(plugin)

        plugin.on_register(self)
        logger.debug("Plugin '%s' registered", plugin.name)
        self.emit(Event(EventType.PLUGIN_LOADED, "eventbus",
                        {"plugin": plugin.name}))

    def unregister(self, plugin_name: str) -> None:
        """Unregister a plugin by name.

        Args:
            plugin_name: The :attr:`TerminalPlugin.name` of the plugin to remove.
        """
        plugin = self._plugins.pop(plugin_name, None)
        if plugin is None:
            logger.warning("Unregister: plugin '%s' not found", plugin_name)
            return
        for subscribers in self._subscribers.values():
            if plugin in subscribers:
                subscribers.remove(plugin)
        plugin.on_unregister()
        logger.debug("Plugin '%s' unregistered", plugin_name)
        self.emit(Event(EventType.PLUGIN_UNLOADED, "eventbus",
                        {"plugin": plugin_name}))

    def get_plugin(self, name: str) -> Optional[TerminalPlugin]:
        """Return the registered plugin with *name*, or ``None``."""
        return self._plugins.get(name)

    @property
    def plugin_names(self) -> List[str]:
        """Names of all currently registered plugins."""
        return list(self._plugins.keys())

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def emit(self, event: Event) -> None:
        """Dispatch *event* to all subscribed plugins.

        Args:
            event: The event to dispatch.
        """
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

        for subscriber in self._subscribers.get(event.type, []):
            try:
                subscriber.on_event(event)
            except Exception:
                logger.exception("Plugin '%s' raised while handling %s",
                                 subscriber.name, event.type.name)
            if event.propagation_stopped:
                break

    # ------------------------------------------------------------------
    # Hook system (extensibility)
    # ------------------------------------------------------------------

    def add_hook(self, hook_name: str, callback: Callable) -> None:
        """Register *callback* under *hook_name* for extensibility.

        Common hook names: ``"pre_render"``, ``"post_screenshot"``.

        Args:
            hook_name: Arbitrary string identifier.
            callback: Callable invoked when :meth:`run_hooks` is called.
        """
        self._hooks[hook_name].append(callback)

    def run_hooks(self, hook_name: str, *args: Any, **kwargs: Any) -> None:
        """Invoke all callbacks registered under *hook_name*.

        Args:
            hook_name: Hook identifier.
            *args: Positional arguments passed to each callback.
            **kwargs: Keyword arguments passed to each callback.
        """
        for callback in self._hooks.get(hook_name, []):
            try:
                callback(*args, **kwargs)
            except Exception:
                logger.exception("Hook '%s' callback raised", hook_name)

    # ------------------------------------------------------------------
    # History / debugging
    # ------------------------------------------------------------------

    @property
    def event_history(self) -> List[Event]:
        """Read-only view of the recent event history."""
        return list(self._event_history)

    def clear_history(self) -> None:
        """Clear the event history buffer."""
        self._event_history.clear()

    def shutdown(self) -> None:
        """Emit :attr:`EventType.SHUTDOWN` and unregister all plugins."""
        self.emit(Event(EventType.SHUTDOWN, "eventbus"))
        for name in list(self._plugins.keys()):
            self.unregister(name)


__all__ = [
    "Event",
    "EventType",
    "EventBus",
    "TerminalPlugin",
]
