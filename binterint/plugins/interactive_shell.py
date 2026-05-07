"""
binterint.plugins.interactive_shell
==================================
Interactive shell plugin that bridges backend input/output with the event bus.

Subscribes to
~~~~~~~~~~~~~
* :attr:`~binterint.event_bus.EventType.PTY_DATA` — writes PTY text to backend.
* :attr:`~binterint.event_bus.EventType.SCREEN_UPDATED` — requests a render frame.
* :attr:`~binterint.event_bus.EventType.SHUTDOWN` — stops input loop and backend.

Emits
~~~~~
* :attr:`~binterint.event_bus.EventType.KEY_PRESS` — when backend receives key input.
* :attr:`~binterint.event_bus.EventType.MOUSE_EVENT` — when backend receives mouse input.
* :attr:`~binterint.event_bus.EventType.RENDER_FRAME` — when screen updates arrive.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Callable, Dict, List, Optional

from ..backends.base import Key, KeyEvent, MouseEvent, TerminalBackend
from ..event_bus import Event, EventBus, EventType, TerminalPlugin

logger = logging.getLogger("binterint.plugins.interactive_shell")


class InteractiveShellPlugin(TerminalPlugin):
    """Interactive terminal shell plugin with async input polling."""

    def __init__(
        self,
        backend: TerminalBackend,
        cols: int = 80,
        rows: int = 24,
        poll_interval: float = 0.001,
    ) -> None:
        self._backend = backend
        self._cols = cols
        self._rows = rows
        self._poll_interval = poll_interval
        self._bus: Optional[EventBus] = None
        self._running = False
        self._started = False
        self._key_bindings: Dict[str, Callable] = {}

    @property
    def name(self) -> str:
        return "interactive_shell"

    def subscribe_to(self) -> List[EventType]:
        return [EventType.PTY_DATA, EventType.SCREEN_UPDATED, EventType.SHUTDOWN]

    def on_register(self, bus: EventBus) -> None:
        self._bus = bus
        self._backend.initialize(self._cols, self._rows)
        self._backend.enable_raw_mode()
        self._started = True

    def on_event(self, event: Event) -> None:
        if event.type == EventType.PTY_DATA:
            self._backend.write(event.data.get("text", ""))
        elif event.type == EventType.SCREEN_UPDATED:
            if self._bus:
                self._bus.emit(Event(EventType.RENDER_FRAME, self.name, dict(event.data)))
        elif event.type == EventType.SHUTDOWN:
            self.stop_input_loop()
            self._teardown_backend()

    def on_unregister(self) -> None:
        self.stop_input_loop()
        self._teardown_backend()

    async def input_loop(self) -> None:
        """Poll backend input events and emit normalized bus events."""
        if not self._started:
            raise RuntimeError("InteractiveShellPlugin must be registered before input_loop")

        self._running = True
        while self._running:
            try:
                evt = self._backend.poll_event()
                if evt is None:
                    await asyncio.sleep(self._poll_interval)
                    continue

                if isinstance(evt, KeyEvent):
                    self._emit_key_event(evt)
                elif isinstance(evt, MouseEvent):
                    self._emit_mouse_event(evt)
            except Exception:
                logger.exception("InteractiveShellPlugin input loop error")
                await asyncio.sleep(self._poll_interval)

    def stop_input_loop(self) -> None:
        """Stop the asynchronous input loop."""
        self._running = False

    def bind_key(self, key: Key, modifiers: int, callback: Callable) -> None:
        """Bind a callback to a specific key/modifier combination."""
        self._key_bindings[f"{key.name}:{modifiers}"] = callback

    def _emit_key_event(self, evt: KeyEvent) -> None:
        if not self._bus:
            return

        callback = self._key_bindings.get(f"{evt.key.name}:{evt.modifiers}")
        if callback:
            try:
                callback()
            except Exception:
                logger.exception("InteractiveShellPlugin key binding callback failed")

        self._bus.emit(
            Event(
                EventType.KEY_PRESS,
                self.name,
                {
                    "key": evt.key,
                    "char": evt.char,
                    "modifiers": evt.modifiers,
                },
            )
        )

    def _emit_mouse_event(self, evt: MouseEvent) -> None:
        if not self._bus:
            return

        self._bus.emit(
            Event(
                EventType.MOUSE_EVENT,
                self.name,
                {
                    "button": evt.button,
                    "action": evt.action,
                    "x": evt.x,
                    "y": evt.y,
                },
            )
        )

    def _teardown_backend(self) -> None:
        if not self._started:
            return

        self._started = False
        try:
            self._backend.disable_raw_mode()
        finally:
            self._backend.shutdown()
