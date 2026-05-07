"""
binterint.plugins.pty_plugin
============================
PTY plugin — spawns a child process via the existing :class:`PtyEngine`,
feeds its output into a pyte stream, and emits events on the bus whenever
new PTY data arrives or the child process exits.

Subscribes to
~~~~~~~~~~~~~
* :attr:`~binterint.event_bus.EventType.KEY_PRESS` — forwards key presses to
  the child process via :meth:`PtyEngine.send_key`.
* :attr:`~binterint.event_bus.EventType.PTY_RESIZED` — resizes the PTY.
* :attr:`~binterint.event_bus.EventType.SHUTDOWN` — kills the child process.

Emits
~~~~~
* :attr:`~binterint.event_bus.EventType.PTY_DATA` — raw text chunk from child.
* :attr:`~binterint.event_bus.EventType.SCREEN_UPDATED` — after the screen buffer
  has been updated with new PTY data.
* :attr:`~binterint.event_bus.EventType.PTY_CLOSED` — when the child process exits.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import List, Optional

import pyte

from ..event_bus import Event, EventBus, EventType, TerminalPlugin
from ..pty_engine import PtyEngine
from ..screen_buffer import TerminalScreen

logger = logging.getLogger("binterint.plugins.pty")


class PtyPlugin(TerminalPlugin):
    """Event-driven PTY plugin.

    Wraps :class:`~binterint.pty_engine.PtyEngine` and
    :class:`~binterint.screen_buffer.TerminalScreen`, emitting events on
    the bus when PTY data arrives or the child process changes state.

    Args:
        cols: Terminal width in columns.
        rows: Terminal height in rows.
    """

    def __init__(self, cols: int = 80, rows: int = 24) -> None:
        self.cols    = cols
        self.rows    = rows
        self.pty     = PtyEngine(cols, rows)
        self.screen  = TerminalScreen(cols, rows)
        self.stream  = pyte.Stream(self.screen)
        self._bus:   Optional[EventBus] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self.last_update = time.time()

    # ------------------------------------------------------------------
    # TerminalPlugin interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "pty"

    def subscribe_to(self) -> List[EventType]:
        return [EventType.KEY_PRESS, EventType.PTY_RESIZED, EventType.SHUTDOWN]

    def on_register(self, bus: EventBus) -> None:
        self._bus = bus

    def on_event(self, event: Event) -> None:
        if event.type == EventType.KEY_PRESS:
            key_seq = event.data.get("sequence") or event.data.get("char", "")
            if key_seq:
                self.pty.send_key(key_seq)

        elif event.type == EventType.PTY_RESIZED:
            cols = event.data.get("cols", self.cols)
            rows = event.data.get("rows", self.rows)
            self.resize(cols, rows)

        elif event.type == EventType.SHUTDOWN:
            self.stop()

    def on_unregister(self) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # Process control
    # ------------------------------------------------------------------

    def spawn(self, cmd: List[str], env: Optional[dict] = None) -> None:
        """Spawn a child process and start the background reader thread.

        Args:
            cmd: Command and arguments list (e.g. ``["htop"]``).
            env: Optional environment variable overrides.
        """
        self.pty.spawn(cmd, env)
        self._running = True
        self._thread  = threading.Thread(target=self._reader_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the reader thread and kill the child process."""
        self._running = False
        try:
            self.pty.kill()
        except Exception:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)

    def resize(self, cols: int, rows: int) -> None:
        """Resize the PTY and screen buffer.

        Args:
            cols: New column count.
            rows: New row count.
        """
        self.cols = cols
        self.rows = rows
        try:
            self.pty.resize(cols, rows)
        except Exception:
            pass
        self.screen.resize(rows, cols)

    def drain(self, timeout: float = 2.0, quiet_period: float = 0.25) -> None:
        """Wait until no PTY data has arrived for *quiet_period* seconds.

        Args:
            timeout: Maximum seconds to wait.
            quiet_period: Silence threshold in seconds.
        """
        start = time.time()
        while time.time() - start < timeout:
            if time.time() - self.last_update > quiet_period:
                time.sleep(0.05)
                if time.time() - self.last_update > quiet_period:
                    return
            time.sleep(0.05)

    def send_key(self, key: str) -> None:
        """Directly send a key sequence to the child process.

        Args:
            key: Raw key sequence string (e.g. ``"q"``, ``"\\x1b"``).
        """
        self.pty.send_key(key)

    def save_screenshot(self, path: str) -> str:
        """Render the current screen and save it as a PNG.

        Args:
            path: Destination file path.

        Returns:
            Absolute path to the saved file.
        """
        from ..renderer import TerminalRenderer  # noqa: PLC0415
        renderer = TerminalRenderer()
        return renderer.save_screenshot(self.screen, path)

    # ------------------------------------------------------------------
    # Internal reader loop
    # ------------------------------------------------------------------

    def _reader_loop(self) -> None:
        """Background thread: read PTY output and emit events."""
        while self._running:
            try:
                output = self.pty.read()
                if output:
                    self.stream.feed(output)
                    self.last_update = time.time()
                    if self._bus:
                        self._bus.emit(Event(EventType.PTY_DATA, self.name,
                                             {"text": output}))
                        self._bus.emit(Event(EventType.SCREEN_UPDATED, self.name,
                                             {"cols": self.cols, "rows": self.rows}))
                time.sleep(0.01)
                if self.pty.process and not self.pty.process.isalive():
                    last = self.pty.read()
                    if last:
                        self.stream.feed(last)
                        if self._bus:
                            self._bus.emit(Event(EventType.PTY_DATA, self.name,
                                                 {"text": last}))
                    if self._bus:
                        self._bus.emit(Event(EventType.PTY_CLOSED, self.name))
                    break
            except Exception:
                logger.exception("PtyPlugin reader loop error")
                break
